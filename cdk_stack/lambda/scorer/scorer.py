"""
Scorer Lambda handler, SQS consumer.

Queries all spans for a completed trace, computes groundedness and
hallucination scores, persists results to the scores table, and emits
CloudWatch metrics that drive the dashboard widgets and alarms.

Scoring approach:
    Groundedness:  Normalised token overlap between answer and source chunks.
    Hallucination: 1 - groundedness when chunks present; hedge-word density otherwise.

Upgrade path: replace compute_groundedness() and compute_hallucination() with
embedding cosine similarity or an LLM-judge call.  The handler is unchanged.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
trace_tbl = dynamodb.Table(os.environ["TRACE_TABLE"])
scores_tbl = dynamodb.Table(os.environ["SCORES_TABLE"])
NS = "AIObservability"

_HEDGE_WORDS: frozenset[str] = frozenset({
    "i think", "i believe", "i'm not sure", "probably", "possibly",
    "might be", "could be", "it seems", "it appears", "generally",
})
_TOKEN_RE: re.Pattern[str] = re.compile(r"\b[a-z]{3,}\b")


def _tokenize(text: str) -> set[str]:
    """Return lowercase word-token set for overlap estimation.

    Args:
        text: Input text to tokenize.

    Returns:
        Set of lowercase tokens with 3+ characters.
    """
    return set(_TOKEN_RE.findall(text.lower()))


def compute_groundedness(answer: str, chunks: list[dict[str, Any]]) -> float:
    """Compute normalised token overlap between answer and source chunks.

    Args:
        answer: LLM-generated answer text.
        chunks: List of enriched chunk dicts containing 'text_preview'.

    Returns:
        Score in [0.0, 1.0] rounded to 4 decimal places.
    """
    if not chunks or not answer:
        return 0.0
    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0
    source_tokens: set[str] = set()
    for chunk in chunks:
        preview = chunk.get("text_preview") or chunk.get("text") or ""
        source_tokens |= _tokenize(preview)
    if not source_tokens:
        return 0.0
    return round(len(answer_tokens & source_tokens) / len(answer_tokens), 4)


def compute_hallucination(answer: str, chunks: list[dict[str, Any]]) -> float:
    """Estimate hallucination likelihood.

    Args:
        answer: LLM-generated answer text.
        chunks: List of enriched chunk dicts.

    Returns:
        Score in [0.0, 1.0] rounded to 4 decimal places.
    """
    if chunks:
        return round(1.0 - compute_groundedness(answer, chunks), 4)
    if not answer:
        return 0.0
    words = answer.lower().split()
    if not words:
        return 0.0
    hedge_count = sum(1 for hw in _HEDGE_WORDS if hw in answer.lower())
    return round(min(hedge_count / max(len(words) / 10, 1), 1.0), 4)


def _fetch_spans(trace_id: str) -> list[dict[str, Any]]:
    """Fetch all spans for a trace from DynamoDB.

    Args:
        trace_id: Trace identifier to query.

    Returns:
        List of span item dicts.

    Raises:
        Exception: Propagates DynamoDB errors to trigger SQS retry.
    """
    resp = trace_tbl.query(KeyConditionExpression=Key("trace_id").eq(trace_id))
    return list(resp.get("Items", []))


def handler(event: dict[str, Any], context: Any) -> None:
    """Lambda entry point for SQS scoring queue messages.

    Args:
        event: SQS event with Records list.
        context: Lambda context object.
    """
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            trace_id: str | None = body.get("trace_id")
            if not trace_id:
                logger.warning("Scorer received message without trace_id, skipping")
                continue

            spans = _fetch_spans(trace_id)
            by_type: dict[str, dict[str, Any]] = {s.get("span_type", ""): s for s in spans}

            answer: str = by_type.get("final_response", {}).get("payload", "") or ""
            ret_span = (
                by_type.get("retrieved_chunks") or by_type.get("retriever") or {}
            )
            chunks: list[dict[str, Any]] = ret_span.get("enriched_chunks", [])

            groundedness = compute_groundedness(answer, chunks)
            hallucination = compute_hallucination(answer, chunks)

            total_cost = sum(
                float(s.get("cost_usd") or 0)
                for s in spans
                if s.get("span_type") == "llm_call"
            )
            llm_span = by_type.get("llm_call", {})
            total_tokens = int(llm_span.get("total_tokens") or 0)
            model = llm_span.get("model", "unknown")

            scores_tbl.put_item(Item={
                "trace_id": trace_id,
                "scored_at": datetime.now(UTC).isoformat(),
                "groundedness": str(groundedness),
                "hallucination": str(hallucination),
                "cost_usd": str(round(total_cost, 6)),
                "total_tokens": total_tokens,
                "model": model,
                "chunk_count": len(chunks),
                "answer_len": len(answer),
            })

            cw.put_metric_data(Namespace=NS, MetricData=[
                {"MetricName": "GroundednessScore",  "Value": groundedness,  "Unit": "None"},
                {"MetricName": "HallucinationScore", "Value": hallucination, "Unit": "None"},
                {"MetricName": "ModelCostUSD",       "Value": total_cost,    "Unit": "None"},
            ])

            logger.info(
                "Scored trace %s: groundedness=%.3f hallucination=%.3f cost=$%.4f",
                trace_id, groundedness, hallucination, total_cost,
            )

        except Exception as exc:
            logger.error(
                "ERROR scoring record %s: %s", record.get("messageId", "?"), exc,
                exc_info=True,
            )
            raise
