"""
Ingest Lambda handler for POST /traces.

Accepts a trace span from the caller, validates all inputs,
persists span-0 to DynamoDB, and fans it out to Kinesis for
downstream processing.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import boto3

# Config module handles all os.getenv access and validates at cold start.
# Inline import here because Lambda packaging does not include src/.
# Each Lambda bundles its own handler; shared logic is duplicated by design
# to keep deployment packages independent.
import os
import re
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
kinesis = boto3.client("kinesis")
trace_table = dynamodb.Table(os.environ["TRACE_TABLE"])
SPAN_STREAM: str = os.environ["SPAN_STREAM"]

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_SAFE_MODEL_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")
_SAFE_VER_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-\.]{1,32}$")
_VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"production", "staging", "development", "test"}
)
_TEMP_MIN: float = 0.0
_TEMP_MAX: float = 2.0


def _validate_identifier(value: str, field: str) -> str:
    """Validate a safe alphanumeric identifier field.

    Args:
        value: The raw string value to validate.
        field: Field name for error messages.

    Returns:
        The validated value.

    Raises:
        ValueError: If value fails the safe identifier pattern.
    """
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"{field} must be 1-128 characters: letters, digits, hyphens, underscores"
        )
    return value


def _validate_temperature(value: Any) -> float:
    """Validate temperature is a float in [0.0, 2.0].

    Args:
        value: Raw value from request body.

    Returns:
        Validated float temperature.

    Raises:
        ValueError: If value is not numeric or is out of range.
    """
    try:
        temp = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"temperature must be a number, got {value!r}")
    if not (_TEMP_MIN <= temp <= _TEMP_MAX):
        raise ValueError(f"temperature must be in [{_TEMP_MIN}, {_TEMP_MAX}], got {temp}")
    return temp


def _parse_request(body: dict[str, Any]) -> dict[str, Any]:
    """Parse and validate ingest request body.

    Args:
        body: Decoded JSON request body.

    Returns:
        Validated field dict ready for span construction.

    Raises:
        ValueError: If any field fails validation.
    """
    raw_tid = body.get("trace_id")
    trace_id = (
        _validate_identifier(raw_tid, "trace_id") if raw_tid else str(uuid.uuid4())
    )

    session_id = "unknown"
    if body.get("session_id"):
        session_id = _validate_identifier(str(body["session_id"]), "session_id")

    model = str(body.get("model", "unknown"))
    if not _SAFE_MODEL_RE.match(model):
        raise ValueError("model contains invalid characters")

    prompt_version = str(body.get("prompt_version", "v1.0"))
    if not _SAFE_VER_RE.match(prompt_version):
        raise ValueError("prompt_version contains invalid characters")

    environment = str(body.get("environment", "production"))
    if environment not in _VALID_ENVIRONMENTS:
        raise ValueError(f"environment must be one of: {', '.join(sorted(_VALID_ENVIRONMENTS))}")

    temperature = _validate_temperature(body.get("temperature", 0.7))

    question = body.get("question", "")
    if not isinstance(question, str):
        raise ValueError("question must be a string")

    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "model": model,
        "prompt_version": prompt_version,
        "environment": environment,
        "temperature": temperature,
        "question": question[:2000],
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point for POST /traces.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    try:
        body = json.loads(event.get("body") or "{}")
        fields = _parse_request(body)

        now = datetime.now(timezone.utc).isoformat()
        ttl = int(time.time()) + (90 * 86400)

        item: dict[str, Any] = {
            "trace_id": fields["trace_id"],
            "span_id": "span-0-user-question",
            "session_id": fields["session_id"],
            "timestamp": now,
            "span_type": "user_question",
            "model": fields["model"],
            "prompt_version": fields["prompt_version"],
            "temperature": str(fields["temperature"]),
            "environment": fields["environment"],
            "payload": fields["question"],
            "status": "captured",
            "ttl": ttl,
        }

        trace_table.put_item(Item=item)
        kinesis.put_record(
            StreamName=SPAN_STREAM,
            Data=json.dumps(item),
            PartitionKey=fields["trace_id"],
        )

        logger.info("Ingested trace %s from session %s", fields["trace_id"], fields["session_id"])
        return _ok({"trace_id": fields["trace_id"], "status": "accepted"})

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Validation error in ingest: %s", exc)
        return _err(400, str(exc))
    except Exception as exc:
        logger.error("Unhandled error in ingest: %s", exc, exc_info=True)
        return _err(500, "Internal server error")


def _ok(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _err(status: int, message: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
