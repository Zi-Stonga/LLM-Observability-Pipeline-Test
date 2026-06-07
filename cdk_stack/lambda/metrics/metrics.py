"""
Metrics Lambda handler, EventBridge scheduled every 5 minutes.

Scans recent LLM call spans with full DynamoDB pagination and emits
aggregate CloudWatch metrics for the operations dashboard.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
trace_tbl = dynamodb.Table(os.environ["TRACE_TABLE"])
NS = "AIObservability"
_WINDOW_MINUTES = 5


def _scan_recent_llm_spans(cutoff: str) -> list[dict[str, Any]]:
    """Paginated scan for llm_call spans newer than cutoff.

    Args:
        cutoff: ISO-format UTC timestamp lower bound.

    Returns:
        All matching span items across all DynamoDB pages.
    """
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = dict(
        FilterExpression=(
            Attr("span_type").eq("llm_call") & Attr("timestamp").gte(cutoff)
        ),
        ProjectionExpression="trace_id,latency_ms,#e,retries,total_tokens,cost_usd",
        ExpressionAttributeNames={"#e": "error"},
    )
    while True:
        resp = trace_tbl.scan(**kwargs)
        items.extend(resp.get("Items", []))
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
        kwargs["ExclusiveStartKey"] = last
    return items


def handler(event: dict[str, Any], context: Any) -> None:
    """Lambda entry point for EventBridge scheduled invocations.

    Args:
        event: EventBridge event (contents not used).
        context: Lambda context object.
    """
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=_WINDOW_MINUTES)).isoformat()
        items = _scan_recent_llm_spans(cutoff)

        if not items:
            logger.info("No LLM spans in last %d minutes, skipping emission", _WINDOW_MINUTES)
            return

        count = len(items)
        latencies = [float(item.get("latency_ms") or 0) for item in items]
        avg_latency = sum(latencies) / count
        error_count = sum(1 for item in items if item.get("error"))
        retry_total = sum(int(item.get("retries") or 0) for item in items)
        token_total = sum(int(item.get("total_tokens") or 0) for item in items)
        cost_total = sum(float(item.get("cost_usd") or 0) for item in items)

        cw.put_metric_data(Namespace=NS, MetricData=[
            {"MetricName": "RequestCount",      "Value": count,              "Unit": "Count"},
            {"MetricName": "PipelineLatencyMs", "Value": avg_latency,        "Unit": "Milliseconds"},
            {"MetricName": "ErrorRate",         "Value": error_count / count, "Unit": "None"},
            {"MetricName": "RetryCount",        "Value": retry_total,        "Unit": "Count"},
            {"MetricName": "TotalTokens",       "Value": token_total,        "Unit": "Count"},
            {"MetricName": "ModelCostUSD",      "Value": cost_total,         "Unit": "None"},
        ])

        logger.info(
            "Metrics emitted: count=%d avg_latency=%.1fms error_rate=%.3f cost=$%.4f",
            count, avg_latency, error_count / count, cost_total,
        )

    except Exception as exc:
        logger.error("ERROR in metrics handler: %s", exc, exc_info=True)
        raise
