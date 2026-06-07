"""Tests for src/config.py: environment variable validation."""

from __future__ import annotations

import pytest


class TestLambdaConfig:
    """LambdaConfig: loads from environment, fails on missing required vars."""

    def test_loads_required_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange: all required vars present via conftest autouse fixture
        import importlib

        import src.config as config_module

        importlib.reload(config_module)
        # Act
        from src.config import config

        # Assert
        assert config.trace_table == "ai-obs-traces"
        assert config.scores_table == "ai-obs-scores"
        assert config.flags_table == "ai-obs-flags"

    def test_optional_vars_default_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange: remove optional vars
        monkeypatch.delenv("SPAN_STREAM", raising=False)
        monkeypatch.delenv("SCORING_QUEUE_URL", raising=False)
        import importlib

        import src.config as config_module

        importlib.reload(config_module)
        from src.config import config

        # Assert
        assert config.span_stream == ""
        assert config.scoring_queue_url == ""
