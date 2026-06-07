"""
Feedback Lambda handler for POST /feedback.

Records thumbs-up or thumbs-down user ratings against a completed trace.
A thumbs-down rating automatically creates a USER_THUMBS_DOWN flag.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
scores_tbl = dynamodb.Table(os.environ["SCORES_TABLE"])
flags_tbl = dynamodb.Table(os.environ["FLAGS_TABLE"])
NS = "AIObservability"

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_VALID_RATINGS: frozenset[str] = frozenset({"thumbs_up", "thumbs_down"})


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for POST /feedback.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    try:
        body = json.loads(event.get("body") or "{}")
        trace_id = str(body.get("trace_id", ""))
        rating = str(body.get("rating", ""))

        if not _SAFE_ID_RE.match(trace_id):
            return _err(400, "trace_id must be 1-128 alphanumeric/dash/underscore characters")

        if rating not in _VALID_RATINGS:
            return _err(400, "rating must be 'thumbs_up' or 'thumbs_down'")

        now = datetime.now(UTC).isoformat()

        scores_tbl.update_item(
            Key={"trace_id": trace_id},
            UpdateExpression="SET user_rating = :r, feedback_ts = :t",
            ExpressionAttributeValues={":r": rating, ":t": now},
        )

        cw.put_metric_data(
            Namespace=NS,
            MetricData=[
                {
                    "MetricName": "ThumbsDown" if rating == "thumbs_down" else "ThumbsUp",
                    "Value": 1,
                    "Unit": "Count",
                }
            ],
        )

        if rating == "thumbs_down":
            flags_tbl.put_item(
                Item={
                    "flag_id": str(uuid.uuid4()),
                    "trace_id": trace_id,
                    "timestamp": now,
                    "rule": "USER_THUMBS_DOWN",
                    "detail": "User downvoted this response.",
                    "severity": "MEDIUM",
                    "status": "open",
                }
            )
            logger.info("Thumbs-down flag created for trace %s", trace_id)
        else:
            logger.info("Thumbs-up recorded for trace %s", trace_id)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "recorded"}),
        }

    except json.JSONDecodeError:
        return _err(400, "Request body must be valid JSON")
    except Exception as exc:
        logger.error("Unhandled error in feedback: %s", exc, exc_info=True)
        return _err(500, "Internal server error")


def _err(status: int, message: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
