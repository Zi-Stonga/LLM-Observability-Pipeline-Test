"""
Centralised configuration loaded from environment variables at Lambda cold start.

All runtime config flows through this module.  No os.getenv() calls elsewhere.
Missing required variables raise a clear error at startup rather than at first use.
"""

from __future__ import annotations

import logging

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class LambdaConfig(BaseSettings):
    """Typed, validated config for all Lambda handlers.

    Populated from environment variables injected by the CDK stack.
    Fails loudly at import time if any required variable is absent.
    """

    trace_table: str = Field(..., alias="TRACE_TABLE")
    scores_table: str = Field(..., alias="SCORES_TABLE")
    flags_table: str = Field(..., alias="FLAGS_TABLE")
    alert_topic_arn: str = Field(..., alias="ALERT_TOPIC_ARN")

    # Optional per-function vars (only present in the relevant Lambda)
    span_stream: str = Field(default="", alias="SPAN_STREAM")
    prompt_registry: str = Field(default="", alias="PROMPT_REGISTRY")
    scoring_queue_url: str = Field(default="", alias="SCORING_QUEUE_URL")

    model_config = {"populate_by_name": True}


# Single instance, imported by handlers, never re-instantiated.
config = LambdaConfig()  # type: ignore[call-arg]
