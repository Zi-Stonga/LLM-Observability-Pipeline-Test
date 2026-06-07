"""Tests for the feedback Lambda handler."""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cdk_stack", "lambda", "feedback"))



def _event(body: dict[str, Any]) -> dict[str, Any]:
    return {"body": json.dumps(body)}


class TestFeedbackHandler:
    """feedback.handler: ratings recorded, flags created, validation enforced."""

    @patch("feedback.cw")
    @patch("feedback.flags_tbl")
    @patch("feedback.scores_tbl")
    def test_thumbs_up_recorded_no_flag(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from feedback import handler
        mock_scores.update_item.return_value = {}
        # Act
        response = handler(_event({"trace_id": "trace-001", "rating": "thumbs_up"}), None)
        # Assert
        assert response["statusCode"] == 200
        mock_flags.put_item.assert_not_called()

    @patch("feedback.cw")
    @patch("feedback.flags_tbl")
    @patch("feedback.scores_tbl")
    def test_thumbs_down_creates_flag(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from feedback import handler
        mock_scores.update_item.return_value = {}
        # Act
        handler(_event({"trace_id": "trace-002", "rating": "thumbs_down"}), None)
        # Assert
        mock_flags.put_item.assert_called_once()
        flag = mock_flags.put_item.call_args[1]["Item"]
        assert flag["rule"] == "USER_THUMBS_DOWN"
        assert flag["trace_id"] == "trace-002"

    @patch("feedback.cw")
    @patch("feedback.flags_tbl")
    @patch("feedback.scores_tbl")
    def test_invalid_rating_returns_400(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from feedback import handler
        # Act
        response = handler(_event({"trace_id": "trace-003", "rating": "meh"}), None)
        # Assert
        assert response["statusCode"] == 400

    @patch("feedback.cw")
    @patch("feedback.flags_tbl")
    @patch("feedback.scores_tbl")
    def test_invalid_trace_id_returns_400(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from feedback import handler
        # Act
        response = handler(
            _event({"trace_id": "bad id with spaces", "rating": "thumbs_up"}), None
        )
        # Assert
        assert response["statusCode"] == 400
