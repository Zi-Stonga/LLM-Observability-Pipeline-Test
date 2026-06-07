"""Tests for the ingest Lambda handler."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cdk_stack", "lambda", "ingest"),
)


def _make_event(body: dict[str, Any]) -> dict[str, Any]:
    return {"body": json.dumps(body)}


class TestIngestHandler:
    """ingest.handler: happy path, validation errors, and service failures."""

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_valid_request_returns_200_with_trace_id(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from ingest import handler

        mock_table.put_item.return_value = {}
        mock_kinesis.put_record.return_value = {}
        event = _make_event(
            {
                "session_id": "sess-001",
                "model": "claude-sonnet",
                "question": "What is the refund policy?",
            }
        )
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "trace_id" in body
        assert body["status"] == "accepted"

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_provided_trace_id_is_preserved(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from ingest import handler

        mock_table.put_item.return_value = {}
        mock_kinesis.put_record.return_value = {}
        event = _make_event({"trace_id": "my-trace-123", "question": "hello"})
        # Act
        response = handler(event, None)
        # Assert
        body = json.loads(response["body"])
        assert body["trace_id"] == "my-trace-123"

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_invalid_temperature_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from ingest import handler

        event = _make_event({"question": "hello", "temperature": 5.0})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400
        assert "temperature" in json.loads(response["body"])["error"]

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_invalid_environment_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from ingest import handler

        event = _make_event({"question": "hello", "environment": "prod"})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_malformed_json_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from ingest import handler

        event = {"body": "not-json"}
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400

    @patch("ingest.kinesis")
    @patch("ingest.trace_table")
    def test_dynamodb_failure_returns_500(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange: mock_table replaces DynamoDB; raising simulates service failure
        from ingest import handler

        mock_table.put_item.side_effect = Exception("DynamoDB error")
        event = _make_event({"question": "hello"})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 500
