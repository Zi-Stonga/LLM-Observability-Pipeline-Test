"""
Processor Lambda handler, Kinesis stream consumer.

Decodes span records from Kinesis, enriches retriever chunks,
calculates per-call token cost, persists to DynamoDB, and enqueues
final_response spans for quality scoring.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
trace_table = dynamodb.Table(os.environ["TRACE_TABLE"])
SCORING_QUEUE: str = os.environ["SCORING_QUEUE_URL"]

# Cost per 1,000 tokens (USD).  Keyed by model name prefix.
# Add new model families here; "default" is the fallback.
COST_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4": {"input": 0.030, "output": 0.060},
    "claude-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-opus": {"input": 0.015, "output": 0.075},
    "claude-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-5": {"input": 0.003, "output": 0.015},
    "claude-3": {"input": 0.003, "output": 0.015},
    "default": {"input": 0.001, "output": 0.002},
}
_SIX_DP = Decimal("0.000001")


def _cost_rates(model: str) -> dict[str, float]:
    """Return cost rates for model, warning when falling back to defaults.

    Args:
        model: Model identifier string from the span.

    Returns:
        Dict with 'input' and 'output' keys containing cost per 1K tokens.
    """
    for key in COST_PER_1K:
        if key != "default" and model.lower().startswith(key):
            return COST_PER_1K[key]
    logger.warning(
        "Unknown model %r, falling back to default cost rates. "
        "Add to COST_PER_1K in processor.py for accurate tracking.",
        model,
    )
    return COST_PER_1K["default"]


def _enrich_retriever_span(span: dict[str, Any]) -> dict[str, Any]:
    """Add enriched_chunks and chunk_count fields to a retriever span.

    Args:
        span: Raw span dict from Kinesis.

    Returns:
        Span dict with enriched_chunks and chunk_count added.
    """
    chunks = span.get("chunks", [])
    enriched = [
        {
            "chunk_id": c.get("chunk_id", f"chunk-{i}"),
            "source": c.get("source", "unknown"),
            "similarity": str(
                Decimal(str(c.get("similarity", 0.0))).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            ),
            "text_preview": c.get("text", "")[:500],
        }
        for i, c in enumerate(chunks)
    ]
    span["enriched_chunks"] = enriched
    span["chunk_count"] = len(enriched)
    return span


def _calculate_cost(span: dict[str, Any]) -> dict[str, Any]:
    """Add cost_usd and total_tokens fields to an llm_call span.

    Args:
        span: Raw llm_call span dict.

    Returns:
        Span dict with cost_usd and total_tokens added.
    """
    rates = _cost_rates(span.get("model", "default"))
    inp = max(0, int(span.get("input_tokens", 0)))
    out = max(0, int(span.get("output_tokens", 0)))
    cost = (inp * rates["input"] + out * rates["output"]) / 1000
    span["cost_usd"] = str(Decimal(str(cost)).quantize(_SIX_DP, rounding=ROUND_HALF_UP).normalize())
    span["total_tokens"] = inp + out
    return span


def handler(event: dict[str, Any], context: Any) -> None:
    """Lambda entry point for Kinesis stream records.

    Args:
        event: Kinesis event with Records list.
        context: Lambda context object.
    """
    for record in event.get("Records", []):
        try:
            span: dict[str, Any] = json.loads(base64.b64decode(record["kinesis"]["data"]))
            span_type: str = span.get("span_type", "")

            if span_type in ("retriever", "retrieved_chunks"):
                span = _enrich_retriever_span(span)

            if span_type == "llm_call":
                span = _calculate_cost(span)

            trace_table.put_item(Item=span)

            if span_type == "final_response":
                sqs.send_message(
                    QueueUrl=SCORING_QUEUE,
                    MessageBody=json.dumps({"trace_id": span["trace_id"]}),
                )
                logger.info("Queued trace %s for scoring", span.get("trace_id"))

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # Non-retriable: structural error in the record itself.
            logger.error("Skipping malformed Kinesis record: %s", exc)
        except Exception as exc:
            logger.error("Retriable error processing record: %s", exc, exc_info=True)
            raise
