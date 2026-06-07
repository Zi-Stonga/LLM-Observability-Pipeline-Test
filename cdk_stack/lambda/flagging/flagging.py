"""
Flagging Lambda handler, DynamoDB Streams consumer on scores_table.

Evaluates four quality rules on every scored trace and creates flag
records when thresholds are breached.  SNS alerts are deduplicated
per rule per batch to prevent alert storms.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
sns_client = boto3.client("sns")
flags_tbl = dynamodb.Table(os.environ["FLAGS_TABLE"])
trace_tbl = dynamodb.Table(os.environ["TRACE_TABLE"])
ALERT_ARN: str = os.environ["ALERT_TOPIC_ARN"]
NS = "AIObservability"

POLICY_KEYWORDS: frozenset[str] = frozenset(
    {"policy", "regulation", "compliance", "rule", "guideline", "procedure"}
)


def _str_attr(image: dict[str, Any], key: str, default: str = "") -> str:
    """Extract a DynamoDB Streams String or Number attribute as a Python str.

    Streams images use typed dicts: {'S': '...'} or {'N': '...'}.

    Args:
        image: DynamoDB Streams NewImage dict.
        key: Attribute name to extract.
        default: Value to return when attribute is absent.

    Returns:
        String value or default.
    """
    attr = image.get(key, {})
    return str(attr.get("S") or attr.get("N") or default)


def _float_attr(image: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Extract a DynamoDB Streams attribute as a Python float.

    Args:
        image: DynamoDB Streams NewImage dict.
        key: Attribute name to extract.
        default: Value to return when attribute is absent or unparseable.

    Returns:
        Float value or default.
    """
    raw = _str_attr(image, key)
    if not raw:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        logger.warning("Cannot parse attribute %r=%r as float; using default", key, raw)
        return default


def _fetch_spans(trace_id: str) -> dict[str, dict[str, Any]]:
    """Fetch all spans for a trace, keyed by span_type.

    Args:
        trace_id: Trace identifier to query.

    Returns:
        Dict mapping span_type to span item.  Empty dict on error.
    """
    try:
        resp = trace_tbl.query(KeyConditionExpression=Key("trace_id").eq(trace_id))
        return {s.get("span_type", ""): s for s in resp.get("Items", [])}
    except Exception as exc:
        logger.error("Failed to fetch spans for trace %s: %s", trace_id, exc)
        return {}


def _write_flag(trace_id: str, rule: str, detail: str, severity: str) -> None:
    """Persist a flag record and emit a CloudWatch FlaggedAnswers metric.

    Args:
        trace_id: Trace the flag belongs to.
        rule: Rule name that triggered the flag.
        detail: Human-readable description of the violation.
        severity: One of CRITICAL, HIGH, MEDIUM, LOW.
    """
    flags_tbl.put_item(Item={
        "flag_id": str(uuid.uuid4()),
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rule": rule,
        "detail": detail,
        "severity": severity,
        "status": "open",
    })
    cw.put_metric_data(
        Namespace=NS,
        MetricData=[{"MetricName": "FlaggedAnswers", "Value": 1, "Unit": "Count"}],
    )
    logger.info("FLAG %s | trace=%s | severity=%s", rule, trace_id, severity)


def handler(event: dict[str, Any], context: Any) -> None:
    """Lambda entry point for DynamoDB Streams records.

    Args:
        event: DynamoDB Streams event with Records list.
        context: Lambda context object.
    """
    pending: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in event.get("Records", []):
        if record.get("eventName") not in ("INSERT", "MODIFY"):
            continue
        try:
            img = record["dynamodb"].get("NewImage", {})
            trace_id = _str_attr(img, "trace_id")
            if not trace_id:
                continue

            groundedness = _float_attr(img, "groundedness", default=1.0)
            hallucination = _float_attr(img, "hallucination", default=0.0)
            cost = _float_attr(img, "cost_usd", default=0.0)

            spans = _fetch_spans(trace_id)
            answer = spans.get("final_response", {}).get("payload", "") or ""
            ret = (spans.get("retrieved_chunks") or spans.get("retriever") or {})
            chunks = ret.get("enriched_chunks", [])

            if not chunks and any(kw in answer.lower() for kw in POLICY_KEYWORDS):
                _write_flag(
                    trace_id, "NO_SOURCE_POLICY_CLAIM",
                    "Answer references policy but no documents retrieved.", "CRITICAL",
                )
                pending["NO_SOURCE_POLICY_CLAIM"].append({"trace_id": trace_id})

            if groundedness < 0.2 and len(answer) > 100:
                _write_flag(
                    trace_id, "LOW_GROUNDEDNESS",
                    f"Groundedness {groundedness:.2f}: possible contradiction.", "HIGH",
                )
                pending["LOW_GROUNDEDNESS"].append(
                    {"trace_id": trace_id, "groundedness": groundedness}
                )

            if hallucination > 0.7:
                _write_flag(
                    trace_id, "HIGH_HALLUCINATION",
                    f"Hallucination {hallucination:.2f}: answer likely fabricated.", "CRITICAL",
                )
                pending["HIGH_HALLUCINATION"].append(
                    {"trace_id": trace_id, "hallucination": hallucination}
                )

            if cost > 0.50:
                _write_flag(trace_id, "COST_SPIKE", f"Request cost ${cost:.4f}", "MEDIUM")
                pending["COST_SPIKE"].append({"trace_id": trace_id, "cost_usd": cost})

        except Exception as exc:
            logger.error("Error evaluating flagging rules: %s", exc, exc_info=True)

    for rule, items in pending.items():
        try:
            sns_client.publish(
                TopicArn=ALERT_ARN,
                Subject=f"[AI Obs] {rule} x{len(items)}",
                Message=json.dumps(
                    {"rule": rule, "count": len(items), "samples": items[:5]}, indent=2
                ),
            )
        except Exception as exc:
            logger.error("SNS publish failed for rule %s: %s", rule, exc)
