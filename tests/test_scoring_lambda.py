"""Tests for the scorer Lambda handler."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cdk_stack", "lambda", "scorer"))

import pytest


def _sqs_event(trace_id: str) -> dict[str, Any]:
    return {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps({"trace_id": trace_id}),
            }
        ]
    }


class TestScorerHandler:
    """scorer.handler: happy path, missing trace_id, and DynamoDB errors."""

    @patch("scorer.cw")
    @patch("scorer.scores_tbl")
    @patch("scorer.trace_tbl")
    def test_valid_trace_is_scored_and_persisted(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from scorer import handler
        mock_trace.query.return_value = {
            "Items": [
                {
                    "span_type": "final_response",
                    "payload": "The refund policy allows returns within 30 days.",
                },
                {
                    "span_type": "retrieved_chunks",
                    "enriched_chunks": [
                        {"text_preview": "refund policy allows returns within 30 days"}
                    ],
                },
                {
                    "span_type": "llm_call",
                    "cost_usd": "0.001",
                    "total_tokens": 100,
                    "model": "claude-sonnet",
                },
            ]
        }
        # Act
        handler(_sqs_event("trace-001"), None)
        # Assert
        mock_scores.put_item.assert_called_once()
        call_item = mock_scores.put_item.call_args[1]["Item"]
        assert call_item["trace_id"] == "trace-001"
        assert float(call_item["groundedness"]) > 0.0
        mock_cw.put_metric_data.assert_called_once()

    @patch("scorer.cw")
    @patch("scorer.scores_tbl")
    @patch("scorer.trace_tbl")
    def test_missing_trace_id_is_skipped(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from scorer import handler
        event = {"Records": [{"messageId": "x", "body": json.dumps({})}]}
        # Act
        handler(event, None)
        # Assert
        mock_trace.query.assert_not_called()
        mock_scores.put_item.assert_not_called()

    @patch("scorer.cw")
    @patch("scorer.scores_tbl")
    @patch("scorer.trace_tbl")
    def test_dynamodb_error_raises_for_sqs_retry(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange: raising simulates a DynamoDB failure; SQS should retry
        from scorer import handler
        mock_trace.query.side_effect = Exception("DynamoDB unavailable")
        # Act / Assert
        with pytest.raises(Exception, match="DynamoDB unavailable"):
            handler(_sqs_event("trace-002"), None)
