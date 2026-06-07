"""Shared pytest fixtures for the LLM observability pipeline test suite."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def set_lambda_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject required Lambda environment variables for all tests."""
    monkeypatch.setenv("TRACE_TABLE", "ai-obs-traces")
    monkeypatch.setenv("SCORES_TABLE", "ai-obs-scores")
    monkeypatch.setenv("FLAGS_TABLE", "ai-obs-flags")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:ai-obs-alerts")
    monkeypatch.setenv("SPAN_STREAM", "ai-obs-spans")
    monkeypatch.setenv("SCORING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue")
    monkeypatch.setenv("PROMPT_REGISTRY", "ai-obs-prompts")
