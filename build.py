"""
Master rebuild script.
Run from your empty repo root: python build.py
Generates the complete project tree conforming to the build standards document.
"""

import os
import sys

ROOT = os.getcwd()


def write(path: str, content: str) -> None:
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  wrote {path}")


FILES: dict[str, str] = {}

# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------
FILES["pyproject.toml"] = """\
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "llm-observability-pipeline"
version = "0.1.0"
description = "Production-grade LLM observability pipeline on AWS"
requires-python = ">=3.12"
dependencies = [
    "aws-cdk-lib>=2.130.0",   # CDK infrastructure definitions
    "constructs>=10.0.0",      # CDK construct base
    "pydantic>=2.6.0",         # Config validation and data models
    "pydantic-settings>=2.2.0", # BaseSettings for env-var config
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",           # Test runner
    "pytest-cov>=5.0.0",       # Coverage reporting
    "pytest-mock>=3.12.0",     # Mock fixtures
    "moto[dynamodb,kinesis,s3,sqs,sns]>=5.0.0",  # AWS service mocks
    "boto3>=1.34.0",           # AWS SDK (Lambda runtime provides this)
    "black>=24.0.0",           # Code formatter
    "ruff>=0.4.0",             # Linter
    "mypy>=1.9.0",             # Static type checker
    "boto3-stubs[dynamodb,kinesis,sqs,sns,cloudwatch]>=1.34.0",  # boto3 type stubs
]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["src"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
exclude = ["cdk_stack/", "tests/"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "cdk_stack/*"]
"""

# ---------------------------------------------------------------------------
# ruff.toml (standalone so ruff picks it up without pyproject.toml parsing)
# ---------------------------------------------------------------------------
FILES["ruff.toml"] = """\
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[lint.isort]
known-first-party = ["src"]
"""

# ---------------------------------------------------------------------------
# .pre-commit-config.yaml
# ---------------------------------------------------------------------------
FILES[".pre-commit-config.yaml"] = """\
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, boto3-stubs]
        args: [--ignore-missing-imports]
"""

# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------
FILES[".gitignore"] = """\
*.pyc
__pycache__/
.venv/
.env
*.egg-info/
dist/
build/
cdk.out/
.cdk.staging/
node_modules/
.DS_Store
*.swp
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/
synth_output.txt
"""

# ---------------------------------------------------------------------------
# .env.example
# ---------------------------------------------------------------------------
FILES[".env.example"] = """\
# Required for CDK deployment
# Pass these as context keys: cdk deploy -c alert_email=... -c allowed_origins=...
ALERT_EMAIL=ops@example.com
ALLOWED_ORIGINS=https://your-app.example.com

# Injected automatically by Lambda at runtime. Do not set locally
TRACE_TABLE=ai-obs-traces
SCORES_TABLE=ai-obs-scores
FLAGS_TABLE=ai-obs-flags
ALERT_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:ai-obs-alerts
SPAN_STREAM=ai-obs-spans
SCORING_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/ai-obs-scoring-queue
PROMPT_REGISTRY=ai-obs-prompts
"""

# ---------------------------------------------------------------------------
# cdk.json
# ---------------------------------------------------------------------------
FILES["cdk.json"] = """\
{
  "app": "python app.py",
  "watch": {
    "include": ["**"],
    "exclude": [
      "README.md", "cdk*.json", "**/__pycache__/**",
      ".venv/**", "**/node_modules/**", "synth_output.txt"
    ]
  },
  "context": {
    "@aws-cdk/aws-apigateway:usagePlanKeyOrderInsensitiveId": true,
    "@aws-cdk/aws-lambda:recognizeLayerVersion": true,
    "@aws-cdk/core:enablePartitionLiterals": true
  }
}
"""

# ---------------------------------------------------------------------------
# requirements.txt (prod, matches Lambda runtime needs)
# ---------------------------------------------------------------------------
FILES["requirements.txt"] = """\
aws-cdk-lib>=2.130.0
constructs>=10.0.0
pydantic>=2.6.0
pydantic-settings>=2.2.0
"""

# ---------------------------------------------------------------------------
# requirements-dev.txt
# ---------------------------------------------------------------------------
FILES["requirements-dev.txt"] = """\
-r requirements.txt
pytest>=8.0.0
pytest-cov>=5.0.0
pytest-mock>=3.12.0
moto[dynamodb,kinesis,s3,sqs,sns]>=5.0.0
boto3>=1.34.0
black>=24.0.0
ruff>=0.4.0
mypy>=1.9.0
boto3-stubs[dynamodb,kinesis,sqs,sns,cloudwatch]>=1.34.0
"""

# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
FILES["app.py"] = """\
\"\"\"CDK application entry point.\"\"\"

import aws_cdk as cdk

from cdk_stack.ai_observability_stack import AiObservabilityStack

app = cdk.App()
AiObservabilityStack(
    app,
    "AiObservabilityStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)
app.synth()
"""

# ---------------------------------------------------------------------------
# src/__init__.py
# ---------------------------------------------------------------------------
FILES["src/__init__.py"] = ""

# ---------------------------------------------------------------------------
# src/config.py
# ---------------------------------------------------------------------------
FILES["src/config.py"] = """\
\"\"\"
Centralised configuration loaded from environment variables at Lambda cold start.

All runtime config flows through this module.  No os.getenv() calls elsewhere.
Missing required variables raise a clear error at startup rather than at first use.
\"\"\"

from __future__ import annotations

import logging

from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class LambdaConfig(BaseSettings):
    \"\"\"Typed, validated config for all Lambda handlers.

    Populated from environment variables injected by the CDK stack.
    Fails loudly at import time if any required variable is absent.
    \"\"\"

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
"""

# ---------------------------------------------------------------------------
# src/models.py
# ---------------------------------------------------------------------------
FILES["src/models.py"] = """\
\"\"\"
Shared domain data models.

All structured data crossing function boundaries uses these types.
No raw dicts passed between modules.
\"\"\"

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass
class Span:
    \"\"\"A single unit of observability data emitted by an LLM pipeline step.

    Spans are the atomic unit of the pipeline.  Every LLM call, retriever
    invocation, and user question produces exactly one span.
    \"\"\"

    trace_id: str
    span_id: str
    span_type: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    session_id: str = "unknown"
    model: str = "unknown"
    payload: str = ""
    status: str = "captured"

    def __repr__(self) -> str:
        return (
            f"Span(trace_id={self.trace_id!r}, "
            f"span_type={self.span_type!r}, "
            f"status={self.status!r})"
        )


@dataclass
class QualityScore:
    \"\"\"Quality scores computed by the scorer for a completed trace.\"\"\"

    trace_id: str
    groundedness: float
    hallucination: float
    cost_usd: Decimal
    total_tokens: int
    model: str
    chunk_count: int
    answer_len: int
    scored_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __repr__(self) -> str:
        return (
            f"QualityScore(trace_id={self.trace_id!r}, "
            f"groundedness={self.groundedness:.3f}, "
            f"hallucination={self.hallucination:.3f})"
        )


@dataclass
class Flag:
    \"\"\"A quality or policy violation flag raised by the flagging engine.\"\"\"

    flag_id: str
    trace_id: str
    rule: str
    detail: str
    severity: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "open"

    def __repr__(self) -> str:
        return (
            f"Flag(trace_id={self.trace_id!r}, "
            f"rule={self.rule!r}, "
            f"severity={self.severity!r})"
        )


@dataclass
class IngestRequest:
    \"\"\"Validated ingest payload from the API Gateway POST /traces body.\"\"\"

    question: str
    session_id: str = "unknown"
    model: str = "unknown"
    prompt_version: str = "v1.0"
    temperature: float = 0.7
    environment: str = "production"
    trace_id: str = ""

    def __repr__(self) -> str:
        return (
            f"IngestRequest(session_id={self.session_id!r}, "
            f"model={self.model!r})"
        )


@dataclass
class ScoringMessage:
    \"\"\"Message placed on the SQS scoring queue by the processor.\"\"\"

    trace_id: str

    def to_dict(self) -> dict[str, Any]:
        \"\"\"Serialize to SQS message body dict.\"\"\"
        return {"trace_id": self.trace_id}

    def __repr__(self) -> str:
        return f"ScoringMessage(trace_id={self.trace_id!r})"
"""

# ---------------------------------------------------------------------------
# src/exceptions.py
# ---------------------------------------------------------------------------
FILES["src/exceptions.py"] = """\
\"\"\"
Domain exception hierarchy.

All internal errors inherit from PipelineError so callers can catch
the base type or specific subtypes as needed.
\"\"\"

from __future__ import annotations


class PipelineError(Exception):
    \"\"\"Base exception for all LLM observability pipeline errors.\"\"\"


class ValidationError(PipelineError):
    \"\"\"Raised when inbound request data fails validation.

    Includes the field name and a human-readable reason so callers
    can return a useful 400 response without leaking internals.
    \"\"\"

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Validation failed for {field!r}: {reason}")


class StorageError(PipelineError):
    \"\"\"Raised when a DynamoDB read or write operation fails.\"\"\"


class StreamError(PipelineError):
    \"\"\"Raised when a Kinesis put_record call fails.\"\"\"


class ScoringError(PipelineError):
    \"\"\"Raised when span scoring cannot be completed.\"\"\"


class FlaggingError(PipelineError):
    \"\"\"Raised when the flagging engine encounters an unrecoverable error.\"\"\"
"""

# ---------------------------------------------------------------------------
# src/validation.py
# ---------------------------------------------------------------------------
FILES["src/validation.py"] = """\
\"\"\"
Input validation utilities used by the ingest and feedback handlers.

All validation logic lives here so it can be unit-tested independently
of Lambda plumbing.
\"\"\"

from __future__ import annotations

import re
import uuid

from src.exceptions import ValidationError

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-]{1,128}$")
_SAFE_MODEL_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-\\.]{1,64}$")
_SAFE_VER_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-\\.]{1,32}$")
_VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"production", "staging", "development", "test"}
)
_VALID_RATINGS: frozenset[str] = frozenset({"thumbs_up", "thumbs_down"})
_TEMP_MIN: float = 0.0
_TEMP_MAX: float = 2.0


def validate_identifier(value: str, field: str) -> str:
    \"\"\"Validate that value is a safe alphanumeric identifier.

    Args:
        value: The string to validate.
        field: Field name used in the error message.

    Returns:
        The validated value unchanged.

    Raises:
        ValidationError: If value does not match the safe identifier pattern.
    \"\"\"
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValidationError(
            field,
            "must be 1-128 characters: letters, digits, hyphens, underscores only",
        )
    return value


def validate_or_generate_trace_id(raw: str | None) -> str:
    \"\"\"Return raw validated, or generate a new UUID if raw is falsy.

    Args:
        raw: Caller-supplied trace_id or None.

    Returns:
        A validated trace_id string.

    Raises:
        ValidationError: If raw is provided but fails identifier validation.
    \"\"\"
    if not raw:
        return str(uuid.uuid4())
    return validate_identifier(raw, "trace_id")


def validate_model(value: str) -> str:
    \"\"\"Validate model identifier format.

    Args:
        value: Model name string to validate.

    Returns:
        The validated model name.

    Raises:
        ValidationError: If the model name contains invalid characters.
    \"\"\"
    if not isinstance(value, str) or not _SAFE_MODEL_RE.match(value):
        raise ValidationError("model", "must be 1-64 alphanumeric/dash/dot characters")
    return value


def validate_prompt_version(value: str) -> str:
    \"\"\"Validate prompt version string format.

    Args:
        value: Prompt version string to validate.

    Returns:
        The validated version string.

    Raises:
        ValidationError: If the version contains invalid characters.
    \"\"\"
    if not isinstance(value, str) or not _SAFE_VER_RE.match(value):
        raise ValidationError(
            "prompt_version", "must be 1-32 alphanumeric/dash/dot characters"
        )
    return value


def validate_environment(value: str) -> str:
    \"\"\"Validate that environment is a recognised deployment target.

    Args:
        value: Environment string to validate.

    Returns:
        The validated environment string.

    Raises:
        ValidationError: If value is not in the allowed set.
    \"\"\"
    if value not in _VALID_ENVIRONMENTS:
        allowed = ", ".join(sorted(_VALID_ENVIRONMENTS))
        raise ValidationError("environment", f"must be one of: {allowed}")
    return value


def validate_temperature(value: float | int | str) -> float:
    \"\"\"Validate that temperature is a float in [0.0, 2.0].

    Args:
        value: Raw temperature value from caller.

    Returns:
        Validated float temperature.

    Raises:
        ValidationError: If value cannot be cast to float or is out of range.
    \"\"\"
    try:
        temp = float(value)
    except (TypeError, ValueError):
        raise ValidationError("temperature", f"must be a number, got {value!r}")
    if not (_TEMP_MIN <= temp <= _TEMP_MAX):
        raise ValidationError(
            "temperature", f"must be between {_TEMP_MIN} and {_TEMP_MAX}, got {temp}"
        )
    return temp


def validate_rating(value: str) -> str:
    \"\"\"Validate that a feedback rating is one of the accepted values.

    Args:
        value: Rating string from caller.

    Returns:
        The validated rating string.

    Raises:
        ValidationError: If value is not a recognised rating.
    \"\"\"
    if value not in _VALID_RATINGS:
        raise ValidationError("rating", "must be 'thumbs_up' or 'thumbs_down'")
    return value
"""

# ---------------------------------------------------------------------------
# src/scoring.py
# ---------------------------------------------------------------------------
FILES["src/scoring.py"] = """\
\"\"\"
Quality scoring logic: groundedness and hallucination estimation.

These functions contain the pure scoring algorithms with no I/O side effects.
Replace _groundedness and _hallucination with embedding-based or LLM-judge
implementations without touching any handler code.
\"\"\"

from __future__ import annotations

import re

_HEDGE_WORDS: frozenset[str] = frozenset(
    {
        "i think",
        "i believe",
        "i'm not sure",
        "probably",
        "possibly",
        "might be",
        "could be",
        "it seems",
        "it appears",
        "generally",
    }
)

_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"\\b[a-z]{3,}\\b")


def _tokenize(text: str) -> set[str]:
    \"\"\"Return a lowercase word-token set for semantic overlap estimation.

    Args:
        text: Input text to tokenize.

    Returns:
        Set of lowercase word tokens (3+ characters).
    \"\"\"
    return set(_TOKEN_PATTERN.findall(text.lower()))


def compute_groundedness(answer: str, chunks: list[dict[str, str]]) -> float:
    \"\"\"Compute normalised token overlap between answer and source chunks.

    A score of 1.0 means every content word in the answer appeared in the
    source material.  0.0 means no overlap at all.

    Args:
        answer: The LLM-generated answer text.
        chunks: List of enriched retriever chunk dicts with 'text_preview' keys.

    Returns:
        Groundedness score in [0.0, 1.0], rounded to 4 decimal places.
    \"\"\"
    if not chunks or not answer:
        return 0.0

    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0

    source_tokens: set[str] = set()
    for chunk in chunks:
        preview = chunk.get("text_preview") or chunk.get("text") or ""
        source_tokens |= _tokenize(preview)

    if not source_tokens:
        return 0.0

    overlap = answer_tokens & source_tokens
    return round(len(overlap) / len(answer_tokens), 4)


def compute_hallucination(answer: str, chunks: list[dict[str, str]]) -> float:
    \"\"\"Estimate hallucination likelihood as a score in [0.0, 1.0].

    When source chunks are present: 1 - groundedness.
    When no source chunks exist: hedge-word density as a fabrication signal.

    Args:
        answer: The LLM-generated answer text.
        chunks: List of enriched retriever chunk dicts.

    Returns:
        Hallucination score in [0.0, 1.0], rounded to 4 decimal places.
    \"\"\"
    if chunks:
        return round(1.0 - compute_groundedness(answer, chunks), 4)

    if not answer:
        return 0.0

    words = answer.lower().split()
    if not words:
        return 0.0

    hedge_count = sum(1 for hw in _HEDGE_WORDS if hw in answer.lower())
    return round(min(hedge_count / max(len(words) / 10, 1), 1.0), 4)
"""

# ---------------------------------------------------------------------------
# cdk_stack/__init__.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/__init__.py"] = "# cdk_stack package\n"

# ---------------------------------------------------------------------------
# cdk_stack/ai_observability_stack.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/ai_observability_stack.py"] = """\
\"\"\"
AI Observability CDK Stack.

Provisions all AWS infrastructure for the LLM observability pipeline:
API Gateway, Lambda (x6), DynamoDB (x4), Kinesis, Firehose, SQS+DLQ,
SNS, S3, CloudWatch dashboards/alarms, WAFv2, and KMS encryption.

Deploy:
    cdk deploy -c alert_email=you@example.com -c allowed_origins=https://app.example.com
\"\"\"

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_logs as logs,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_sqs as sqs,
    aws_wafv2 as wafv2,
)
from constructs import Construct

_LAMBDA_RUNTIME = lambda_.Runtime.PYTHON_3_12
_CW_NAMESPACE = "AIObservability"


class AiObservabilityStack(Stack):
    \"\"\"Root CDK stack for the LLM observability pipeline.\"\"\"

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        alert_email = self._require_context("alert_email")
        cors_origins = self._require_origins()

        storage_key = self._make_kms_key("StorageKey", "DynamoDB + S3 + SQS + SNS")
        stream_key = self._make_kms_key("StreamKey", "Kinesis stream")

        raw_bucket = self._make_bucket(storage_key)
        tables = self._make_tables(storage_key)
        span_stream = self._make_kinesis(stream_key)
        self._make_firehose(raw_bucket, span_stream, storage_key, stream_key)
        scoring_dlq, scoring_queue = self._make_queues(storage_key)
        alert_topic = self._make_sns(alert_email, storage_key)

        roles = self._make_roles(tables, span_stream, scoring_queue, scoring_dlq,
                                  raw_bucket, alert_topic, storage_key, stream_key)

        fns = self._make_lambdas(roles, tables, span_stream, scoring_queue, alert_topic)
        self._wire_event_sources(fns, span_stream, scoring_queue, tables["scores"])

        api = self._make_api(fns, cors_origins)
        self._make_waf(api)
        self._make_dashboard(scoring_dlq)
        self._make_alarms(alert_topic, scoring_dlq)

        logs.LogGroup(
            self, "TraceLogGroup",
            log_group_name="/ai-obs/traces",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        cdk.CfnOutput(self, "ApiEndpoint", value=api.url)
        cdk.CfnOutput(self, "RawBucket", value=raw_bucket.bucket_name)
        cdk.CfnOutput(self, "AlertTopicArn", value=alert_topic.topic_arn)
        cdk.CfnOutput(self, "ScoringDLQUrl", value=scoring_dlq.queue_url)
        cdk.CfnOutput(self, "StorageKeyArn", value=storage_key.key_arn)
        cdk.CfnOutput(
            self, "DashboardUrl",
            value=(
                f"https://{self.region}.console.aws.amazon.com"
                "/cloudwatch/home#dashboards:name=AI-Pipeline-Observability"
            ),
        )

    # --------------------------------------------------------------------------
    # Context helpers
    # --------------------------------------------------------------------------

    def _require_context(self, key: str) -> str:
        value = self.node.try_get_context(key)
        if not value:
            raise ValueError(
                f"CDK context key '{key}' is required. "
                f"Pass -c {key}=<value> to cdk deploy."
            )
        return str(value)

    def _require_origins(self) -> list[str]:
        raw = self.node.try_get_context("allowed_origins") or ""
        origins = [o.strip() for o in str(raw).split(",") if o.strip()]
        if not origins:
            raise ValueError(
                "CDK context key 'allowed_origins' is required (comma-separated). "
                "Pass -c allowed_origins=https://your-app.example.com"
            )
        return origins

    # --------------------------------------------------------------------------
    # Resource factories
    # --------------------------------------------------------------------------

    def _make_kms_key(self, construct_id: str, purpose: str) -> kms.Key:
        \"\"\"Create a CMK with automatic rotation for the given purpose.\"\"\"
        return kms.Key(
            self, construct_id,
            description=f"AI Obs pipeline: {purpose} encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _make_bucket(self, key: kms.Key) -> s3.Bucket:
        \"\"\"Create the raw trace archive bucket with encryption and access controls.\"\"\"
        return s3.Bucket(
            self, "RawTraceBucket",
            bucket_name=f"ai-obs-raw-traces-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="Glacier",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _make_tables(self, key: kms.Key) -> dict[str, dynamodb.Table]:
        \"\"\"Create all four DynamoDB tables with streams and encryption.\"\"\"
        enc = dynamodb.TableEncryption.CUSTOMER_MANAGED

        trace = dynamodb.Table(
            self, "TraceTable",
            table_name="ai-obs-traces",
            partition_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="span_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            time_to_live_attribute="ttl",
            encryption=enc,
            encryption_key=key,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        trace.add_global_secondary_index(
            index_name="session-index",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
        )

        scores = dynamodb.Table(
            self, "ScoresTable",
            table_name="ai-obs-scores",
            partition_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            encryption=enc,
            encryption_key=key,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        flags = dynamodb.Table(
            self, "FlagsTable",
            table_name="ai-obs-flags",
            partition_key=dynamodb.Attribute(name="flag_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=enc,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        prompts = dynamodb.Table(
            self, "PromptRegistry",
            table_name="ai-obs-prompts",
            partition_key=dynamodb.Attribute(name="prompt_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="version", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=enc,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        return {"trace": trace, "scores": scores, "flags": flags, "prompts": prompts}

    def _make_kinesis(self, key: kms.Key) -> kinesis.Stream:
        \"\"\"Create the span stream with 7-day retention and KMS encryption.\"\"\"
        return kinesis.Stream(
            self, "SpanStream",
            stream_name="ai-obs-spans",
            shard_count=2,
            retention_period=Duration.hours(168),
            encryption=kinesis.StreamEncryption.KMS,
            encryption_key=key,
        )

    def _make_firehose(
        self,
        bucket: s3.Bucket,
        stream: kinesis.Stream,
        storage_key: kms.Key,
        stream_key: kms.Key,
    ) -> None:
        \"\"\"Create the Kinesis Firehose delivery stream to S3.\"\"\"
        role = iam.Role(
            self, "FirehoseRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        bucket.grant_write(role)
        stream.grant_read(role)
        storage_key.grant_encrypt_decrypt(role)
        stream_key.grant_decrypt(role)

        firehose.CfnDeliveryStream(
            self, "SpanFirehose",
            delivery_stream_name="ai-obs-span-firehose",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=stream.stream_arn,
                role_arn=role.role_arn,
            ),
            s3_destination_configuration=firehose.CfnDeliveryStream.S3DestinationConfigurationProperty(
                bucket_arn=bucket.bucket_arn,
                role_arn=role.role_arn,
                prefix="spans/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/",
                error_output_prefix="errors/!{firehose:error-output-type}/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60, size_in_m_bs=5
                ),
                compression_format="GZIP",
                encryption_configuration=firehose.CfnDeliveryStream.EncryptionConfigurationProperty(
                    kms_encryption_config=firehose.CfnDeliveryStream.KMSEncryptionConfigProperty(
                        awskms_key_arn=storage_key.key_arn
                    )
                ),
            ),
        )

    def _make_queues(self, key: kms.Key) -> tuple[sqs.Queue, sqs.Queue]:
        \"\"\"Create the scoring queue and its dead-letter queue, both encrypted.\"\"\"
        dlq = sqs.Queue(
            self, "ScoringDLQ",
            queue_name="ai-obs-scoring-dlq",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            retention_period=Duration.days(14),
        )
        queue = sqs.Queue(
            self, "ScoringQueue",
            queue_name="ai-obs-scoring-queue",
            visibility_timeout=Duration.seconds(120),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )
        return dlq, queue

    def _make_sns(self, alert_email: str, key: kms.Key) -> sns.Topic:
        \"\"\"Create the SNS alert topic with email subscription.\"\"\"
        topic = sns.Topic(
            self, "AlertTopic",
            topic_name="ai-obs-alerts",
            display_name="AI Observability Alerts",
            master_key=key,
        )
        topic.add_subscription(sns_subs.EmailSubscription(alert_email))
        return topic

    def _cw_put_policy(self) -> iam.PolicyStatement:
        \"\"\"Return a namespace-scoped CloudWatch PutMetricData policy statement.\"\"\"
        return iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
            conditions={"StringEquals": {"cloudwatch:namespace": _CW_NAMESPACE}},
        )

    def _make_roles(
        self,
        tables: dict[str, dynamodb.Table],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        dlq: sqs.Queue,
        bucket: s3.Bucket,
        topic: sns.Topic,
        storage_key: kms.Key,
        stream_key: kms.Key,
    ) -> dict[str, iam.Role]:
        \"\"\"Create six least-privilege IAM roles, one per Lambda function.\"\"\"
        base = [iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )]
        cw = self._cw_put_policy()

        def role(id_: str) -> iam.Role:
            return iam.Role(
                self, id_,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=base,
            )

        ingest = role("IngestRole")
        tables["trace"].grant_write_data(ingest)
        stream.grant_write(ingest)
        tables["prompts"].grant_read_data(ingest)
        storage_key.grant_encrypt_decrypt(ingest)
        stream_key.grant_encrypt(ingest)

        processor = role("ProcessorRole")
        stream.grant_read(processor)
        tables["trace"].grant_write_data(processor)
        queue.grant_send_messages(processor)
        storage_key.grant_encrypt_decrypt(processor)
        stream_key.grant_decrypt(processor)

        scorer = role("ScorerRole")
        tables["trace"].grant_read_data(scorer)
        tables["scores"].grant_write_data(scorer)
        queue.grant_consume_messages(scorer)
        storage_key.grant_encrypt_decrypt(scorer)
        scorer.add_to_policy(cw)

        flagging = role("FlaggingRole")
        tables["trace"].grant_read_data(flagging)
        tables["scores"].grant_stream_read(flagging)
        tables["flags"].grant_write_data(flagging)
        topic.grant_publish(flagging)
        storage_key.grant_encrypt_decrypt(flagging)
        flagging.add_to_policy(cw)

        feedback = role("FeedbackRole")
        tables["scores"].grant_write_data(feedback)
        tables["flags"].grant_write_data(feedback)
        storage_key.grant_encrypt_decrypt(feedback)
        feedback.add_to_policy(cw)

        metrics = role("MetricsRole")
        tables["trace"].grant_read_data(metrics)
        storage_key.grant_decrypt(metrics)
        metrics.add_to_policy(cw)

        return {
            "ingest": ingest,
            "processor": processor,
            "scorer": scorer,
            "flagging": flagging,
            "feedback": feedback,
            "metrics": metrics,
        }

    def _make_lambdas(
        self,
        roles: dict[str, iam.Role],
        tables: dict[str, dynamodb.Table],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        topic: sns.Topic,
    ) -> dict[str, lambda_.Function]:
        \"\"\"Create all six Lambda functions with X-Ray tracing enabled.\"\"\"
        base_env = {
            "TRACE_TABLE": tables["trace"].table_name,
            "SCORES_TABLE": tables["scores"].table_name,
            "FLAGS_TABLE": tables["flags"].table_name,
            "ALERT_TOPIC_ARN": topic.topic_arn,
        }

        def fn(
            id_: str,
            name: str,
            handler: str,
            asset: str,
            env: dict[str, str],
            role: iam.Role,
            timeout: int = 30,
            memory: int = 256,
        ) -> lambda_.Function:
            return lambda_.Function(
                self, id_,
                function_name=name,
                runtime=_LAMBDA_RUNTIME,
                handler=handler,
                code=lambda_.Code.from_asset(asset),
                role=role,
                timeout=Duration.seconds(timeout),
                memory_size=memory,
                environment=env,
                tracing=lambda_.Tracing.ACTIVE,
            )

        ingest = fn(
            "IngestFn", "ai-obs-ingest", "ingest.handler",
            "cdk_stack/lambda/ingest",
            {**base_env, "SPAN_STREAM": stream.stream_name,
             "PROMPT_REGISTRY": tables["prompts"].table_name},
            roles["ingest"],
        )
        processor = fn(
            "SpanProcessorFn", "ai-obs-span-processor", "processor.handler",
            "cdk_stack/lambda/processor",
            {**base_env, "SCORING_QUEUE_URL": queue.queue_url},
            roles["processor"], timeout=60, memory=512,
        )
        scorer = fn(
            "ScorerFn", "ai-obs-scorer", "scorer.handler",
            "cdk_stack/lambda/scorer",
            base_env, roles["scorer"], timeout=120, memory=512,
        )
        flagging = fn(
            "FlaggingFn", "ai-obs-flagging", "flagging.handler",
            "cdk_stack/lambda/flagging",
            base_env, roles["flagging"], timeout=60,
        )
        feedback = fn(
            "FeedbackFn", "ai-obs-feedback", "feedback.handler",
            "cdk_stack/lambda/feedback",
            base_env, roles["feedback"], timeout=30, memory=128,
        )
        metrics_fn = fn(
            "MetricsFn", "ai-obs-metrics", "metrics.handler",
            "cdk_stack/lambda/metrics",
            base_env, roles["metrics"], timeout=300, memory=512,
        )

        rule = events.Rule(
            self, "MetricsSchedule",
            rule_name="ai-obs-metrics-schedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )
        rule.add_target(targets.LambdaFunction(metrics_fn))

        return {
            "ingest": ingest,
            "processor": processor,
            "scorer": scorer,
            "flagging": flagging,
            "feedback": feedback,
            "metrics": metrics_fn,
        }

    def _wire_event_sources(
        self,
        fns: dict[str, lambda_.Function],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        scores_table: dynamodb.Table,
    ) -> None:
        \"\"\"Attach Kinesis, SQS, and DynamoDB Streams event sources.\"\"\"
        fns["processor"].add_event_source(
            lambda_events.KinesisEventSource(
                stream,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=50,
                bisect_batch_on_error=True,
                retry_attempts=3,
            )
        )
        fns["scorer"].add_event_source(
            lambda_events.SqsEventSource(queue, batch_size=5)
        )
        fns["flagging"].add_event_source(
            lambda_events.DynamoEventSource(
                scores_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_function_error=True,
                retry_attempts=3,
            )
        )

    def _make_api(
        self,
        fns: dict[str, lambda_.Function],
        cors_origins: list[str],
    ) -> apigw.RestApi:
        \"\"\"Create API Gateway with access logging, throttling, and scoped CORS.\"\"\"
        api = apigw.RestApi(
            self, "ObsApi",
            rest_api_name="ai-observability-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=cors_origins,
                allow_methods=["POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Api-Key"],
                max_age=Duration.hours(1),
            ),
            deploy_options=apigw.StageOptions(
                stage_name="v1",
                throttling_rate_limit=1000,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                metrics_enabled=True,
                tracing_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(
                    logs.LogGroup(
                        self, "ApiAccessLog",
                        log_group_name="/ai-obs/api-access",
                        retention=logs.RetentionDays.THREE_MONTHS,
                        removal_policy=RemovalPolicy.DESTROY,
                    )
                ),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True, http_method=True, ip=True, protocol=True,
                    request_time=True, resource_path=True, response_length=True,
                    status=True, user=True,
                ),
            ),
        )

        traces_r = api.root.add_resource("traces")
        traces_r.add_method(
            "POST", apigw.LambdaIntegration(fns["ingest"]), api_key_required=True
        )

        feedback_r = api.root.add_resource("feedback")
        feedback_r.add_method(
            "POST", apigw.LambdaIntegration(fns["feedback"]), api_key_required=True
        )

        api_key = api.add_api_key("ObsApiKey", api_key_name="ai-obs-api-key")
        plan = api.add_usage_plan(
            "ObsUsagePlan",
            name="ai-obs-usage-plan",
            throttle=apigw.ThrottleSettings(rate_limit=1000, burst_limit=200),
        )
        plan.add_api_key(api_key)
        plan.add_api_stage(stage=api.deployment_stage)

        return api

    def _make_waf(self, api: apigw.RestApi) -> None:
        \"\"\"Attach WAFv2 WebACL with OWASP managed rules and IP rate limiting.\"\"\"
        waf = wafv2.CfnWebACL(
            self, "ApiWaf",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="ai-obs-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                self._waf_managed_rule("CommonRuleSet", 1, "AWSManagedRulesCommonRuleSet"),
                self._waf_managed_rule("KnownBadInputs", 2, "AWSManagedRulesKnownBadInputsRuleSet"),
                self._waf_rate_rule("IPRateLimit", 3, limit=2000),
            ],
        )
        wafv2.CfnWebACLAssociation(
            self, "ApiWafAssociation",
            resource_arn=(
                f"arn:aws:apigateway:{self.region}::"
                f"/restapis/{api.rest_api_id}/stages/v1"
            ),
            web_acl_arn=waf.attr_arn,
        )

    def _waf_managed_rule(
        self, name: str, priority: int, managed_name: str
    ) -> wafv2.CfnWebACL.RuleProperty:
        return wafv2.CfnWebACL.RuleProperty(
            name=name,
            priority=priority,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS", name=managed_name
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name,
                sampled_requests_enabled=True,
            ),
        )

    def _waf_rate_rule(
        self, name: str, priority: int, limit: int
    ) -> wafv2.CfnWebACL.RuleProperty:
        return wafv2.CfnWebACL.RuleProperty(
            name=name,
            priority=priority,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=limit, aggregate_key_type="IP"
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name,
                sampled_requests_enabled=True,
            ),
        )

    def _make_dashboard(self, dlq: sqs.Queue) -> None:
        \"\"\"Create the CloudWatch operations dashboard.\"\"\"
        ns = _CW_NAMESPACE
        dashboard = cloudwatch.Dashboard(
            self, "ObsDashboard", dashboard_name="AI-Pipeline-Observability"
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Requests/min",
                left=[cloudwatch.Metric(namespace=ns, metric_name="RequestCount",
                      statistic="Sum", period=Duration.minutes(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Avg Latency (ms)",
                left=[cloudwatch.Metric(namespace=ns, metric_name="PipelineLatencyMs",
                      statistic="Average", period=Duration.minutes(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Hallucination Score",
                left=[cloudwatch.Metric(namespace=ns, metric_name="HallucinationScore",
                      statistic="Average", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Groundedness Score",
                left=[cloudwatch.Metric(namespace=ns, metric_name="GroundednessScore",
                      statistic="Average", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Model Cost (USD)",
                left=[cloudwatch.Metric(namespace=ns, metric_name="ModelCostUSD",
                      statistic="Sum", period=Duration.hours(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Flagged Answers",
                left=[cloudwatch.Metric(namespace=ns, metric_name="FlaggedAnswers",
                      statistic="Sum", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Scoring DLQ Depth",
                left=[cloudwatch.Metric(
                    namespace="AWS/SQS",
                    metric_name="ApproximateNumberOfMessagesVisible",
                    dimensions_map={"QueueName": dlq.queue_name},
                    statistic="Maximum", period=Duration.minutes(5),
                )], width=8,
            ),
        )

    def _make_alarms(self, topic: sns.Topic, dlq: sqs.Queue) -> None:
        \"\"\"Create CloudWatch alarms wired to the SNS alert topic.\"\"\"
        ns = _CW_NAMESPACE

        alarm_specs = [
            ("HallucinationAlarm", "ai-obs-high-hallucination", ns,
             "HallucinationScore", 0.5, 2, "Average",
             "Average hallucination > 0.5 over two 5-min windows"),
            ("ErrorRateAlarm", "ai-obs-high-error-rate", ns,
             "ErrorRate", 0.05, 3, "Average",
             "Error rate > 5% over three 5-min windows"),
            ("FlagAlarm", "ai-obs-flag-spike", ns,
             "FlaggedAnswers", 10, 1, "Sum",
             "More than 10 flagged answers in a single 5-min window"),
        ]

        for alarm_id, name, namespace, metric_name, threshold, periods, stat, desc in alarm_specs:
            alarm = cloudwatch.Alarm(
                self, alarm_id,
                alarm_name=name,
                alarm_description=desc,
                metric=cloudwatch.Metric(
                    namespace=namespace, metric_name=metric_name,
                    statistic=stat, period=Duration.minutes(5),
                ),
                threshold=threshold,
                evaluation_periods=periods,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(cw_actions.SnsAction(topic))

        dlq_alarm = cloudwatch.Alarm(
            self, "DLQAlarm",
            alarm_name="ai-obs-dlq-messages",
            alarm_description="Messages in scoring DLQ: investigate poison spans",
            metric=cloudwatch.Metric(
                namespace="AWS/SQS",
                metric_name="ApproximateNumberOfMessagesVisible",
                dimensions_map={"QueueName": dlq.queue_name},
                statistic="Maximum", period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dlq_alarm.add_alarm_action(cw_actions.SnsAction(topic))
"""

# ---------------------------------------------------------------------------
# Lambda __init__ files
# ---------------------------------------------------------------------------
for fn_name in ("ingest", "processor", "scorer", "flagging", "feedback", "metrics"):
    FILES[f"cdk_stack/lambda/{fn_name}/__init__.py"] = "# Lambda handler package\n"

# ---------------------------------------------------------------------------
# cdk_stack/lambda/ingest/ingest.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/ingest/ingest.py"] = """\
\"\"\"
Ingest Lambda handler for POST /traces.

Accepts a trace span from the caller, validates all inputs,
persists span-0 to DynamoDB, and fans it out to Kinesis for
downstream processing.
\"\"\"

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

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-]{1,128}$")
_SAFE_MODEL_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-\\.]{1,64}$")
_SAFE_VER_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-\\.]{1,32}$")
_VALID_ENVIRONMENTS: frozenset[str] = frozenset(
    {"production", "staging", "development", "test"}
)
_TEMP_MIN: float = 0.0
_TEMP_MAX: float = 2.0


def _validate_identifier(value: str, field: str) -> str:
    \"\"\"Validate a safe alphanumeric identifier field.

    Args:
        value: The raw string value to validate.
        field: Field name for error messages.

    Returns:
        The validated value.

    Raises:
        ValueError: If value fails the safe identifier pattern.
    \"\"\"
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"{field} must be 1-128 characters: letters, digits, hyphens, underscores"
        )
    return value


def _validate_temperature(value: Any) -> float:
    \"\"\"Validate temperature is a float in [0.0, 2.0].

    Args:
        value: Raw value from request body.

    Returns:
        Validated float temperature.

    Raises:
        ValueError: If value is not numeric or is out of range.
    \"\"\"
    try:
        temp = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"temperature must be a number, got {value!r}")
    if not (_TEMP_MIN <= temp <= _TEMP_MAX):
        raise ValueError(f"temperature must be in [{_TEMP_MIN}, {_TEMP_MAX}], got {temp}")
    return temp


def _parse_request(body: dict[str, Any]) -> dict[str, Any]:
    \"\"\"Parse and validate ingest request body.

    Args:
        body: Decoded JSON request body.

    Returns:
        Validated field dict ready for span construction.

    Raises:
        ValueError: If any field fails validation.
    \"\"\"
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
    \"\"\"Lambda entry point for POST /traces.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    \"\"\"
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
"""

# ---------------------------------------------------------------------------
# cdk_stack/lambda/processor/processor.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/processor/processor.py"] = """\
\"\"\"
Processor Lambda handler, Kinesis stream consumer.

Decodes span records from Kinesis, enriches retriever chunks,
calculates per-call token cost, persists to DynamoDB, and enqueues
final_response spans for quality scoring.
\"\"\"

from __future__ import annotations

import base64
import json
import logging
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")
trace_table = dynamodb.Table(os.environ["TRACE_TABLE"])
SCORING_QUEUE: str = os.environ["SCORING_QUEUE_URL"]

# Cost per 1,000 tokens (USD).  Keyed by model name prefix.
# Add new model families here; "default" is the fallback.
COST_PER_1K: dict[str, dict[str, float]] = {
    "gpt-4o-mini":   {"input": 0.00015, "output": 0.00060},
    "gpt-4o":        {"input": 0.005,   "output": 0.015},
    "gpt-4":         {"input": 0.030,   "output": 0.060},
    "claude-haiku":  {"input": 0.00025, "output": 0.00125},
    "claude-opus":   {"input": 0.015,   "output": 0.075},
    "claude-sonnet": {"input": 0.003,   "output": 0.015},
    "claude-3-5":    {"input": 0.003,   "output": 0.015},
    "claude-3":      {"input": 0.003,   "output": 0.015},
    "default":       {"input": 0.001,   "output": 0.002},
}
_SIX_DP = Decimal("0.000001")


def _cost_rates(model: str) -> dict[str, float]:
    \"\"\"Return cost rates for model, warning when falling back to defaults.

    Args:
        model: Model identifier string from the span.

    Returns:
        Dict with 'input' and 'output' keys containing cost per 1K tokens.
    \"\"\"
    for key in COST_PER_1K:
        if key != "default" and model.lower().startswith(key):
            return COST_PER_1K[key]
    logger.warning(
        "Unknown model %r, falling back to default cost rates. "
        "Add to COST_PER_1K in processor.py for accurate tracking.",
        model,
    )
    return COST_PER_1K["default"]


def _enrich_retriever_span(span: dict[str, Any]) -> dict[str, Any]:
    \"\"\"Add enriched_chunks and chunk_count fields to a retriever span.

    Args:
        span: Raw span dict from Kinesis.

    Returns:
        Span dict with enriched_chunks and chunk_count added.
    \"\"\"
    chunks = span.get("chunks", [])
    enriched = [
        {
            "chunk_id": c.get("chunk_id", f"chunk-{i}"),
            "source": c.get("source", "unknown"),
            "similarity": str(
                Decimal(str(c.get("similarity", 0.0))).quantize(
                    Decimal("0.0001"), rounding=ROUND_HALF_UP
                )
            ),
            "text_preview": c.get("text", "")[:500],
        }
        for i, c in enumerate(chunks)
    ]
    span["enriched_chunks"] = enriched
    span["chunk_count"] = len(enriched)
    return span


def _calculate_cost(span: dict[str, Any]) -> dict[str, Any]:
    \"\"\"Add cost_usd and total_tokens fields to an llm_call span.

    Args:
        span: Raw llm_call span dict.

    Returns:
        Span dict with cost_usd and total_tokens added.
    \"\"\"
    rates = _cost_rates(span.get("model", "default"))
    inp = max(0, int(span.get("input_tokens", 0)))
    out = max(0, int(span.get("output_tokens", 0)))
    cost = (inp * rates["input"] + out * rates["output"]) / 1000
    span["cost_usd"] = str(
        Decimal(str(cost)).quantize(_SIX_DP, rounding=ROUND_HALF_UP).normalize()
    )
    span["total_tokens"] = inp + out
    return span


def handler(event: dict[str, Any], context: Any) -> None:
    \"\"\"Lambda entry point for Kinesis stream records.

    Args:
        event: Kinesis event with Records list.
        context: Lambda context object.
    \"\"\"
    for record in event.get("Records", []):
        try:
            span: dict[str, Any] = json.loads(
                base64.b64decode(record["kinesis"]["data"])
            )
            span_type: str = span.get("span_type", "")

            if span_type in ("retriever", "retrieved_chunks"):
                span = _enrich_retriever_span(span)

            if span_type == "llm_call":
                span = _calculate_cost(span)

            trace_table.put_item(Item=span)

            if span_type == "final_response":
                sqs.send_message(
                    QueueUrl=SCORING_QUEUE,
                    MessageBody=json.dumps({"trace_id": span["trace_id"]}),
                )
                logger.info("Queued trace %s for scoring", span.get("trace_id"))

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # Non-retriable: structural error in the record itself.
            logger.error("Skipping malformed Kinesis record: %s", exc)
        except Exception as exc:
            logger.error("Retriable error processing record: %s", exc, exc_info=True)
            raise
"""

# ---------------------------------------------------------------------------
# cdk_stack/lambda/scorer/scorer.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/scorer/scorer.py"] = """\
\"\"\"
Scorer Lambda handler, SQS consumer.

Queries all spans for a completed trace, computes groundedness and
hallucination scores, persists results to the scores table, and emits
CloudWatch metrics that drive the dashboard widgets and alarms.

Scoring approach:
    Groundedness:  Normalised token overlap between answer and source chunks.
    Hallucination: 1 - groundedness when chunks present; hedge-word density otherwise.

Upgrade path: replace compute_groundedness() and compute_hallucination() with
embedding cosine similarity or an LLM-judge call.  The handler is unchanged.
\"\"\"

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
trace_tbl = dynamodb.Table(os.environ["TRACE_TABLE"])
scores_tbl = dynamodb.Table(os.environ["SCORES_TABLE"])
NS = "AIObservability"

_HEDGE_WORDS: frozenset[str] = frozenset({
    "i think", "i believe", "i'm not sure", "probably", "possibly",
    "might be", "could be", "it seems", "it appears", "generally",
})
_TOKEN_RE: re.Pattern[str] = re.compile(r"\\b[a-z]{3,}\\b")


def _tokenize(text: str) -> set[str]:
    \"\"\"Return lowercase word-token set for overlap estimation.

    Args:
        text: Input text to tokenize.

    Returns:
        Set of lowercase tokens with 3+ characters.
    \"\"\"
    return set(_TOKEN_RE.findall(text.lower()))


def compute_groundedness(answer: str, chunks: list[dict[str, Any]]) -> float:
    \"\"\"Compute normalised token overlap between answer and source chunks.

    Args:
        answer: LLM-generated answer text.
        chunks: List of enriched chunk dicts containing 'text_preview'.

    Returns:
        Score in [0.0, 1.0] rounded to 4 decimal places.
    \"\"\"
    if not chunks or not answer:
        return 0.0
    answer_tokens = _tokenize(answer)
    if not answer_tokens:
        return 0.0
    source_tokens: set[str] = set()
    for chunk in chunks:
        preview = chunk.get("text_preview") or chunk.get("text") or ""
        source_tokens |= _tokenize(preview)
    if not source_tokens:
        return 0.0
    return round(len(answer_tokens & source_tokens) / len(answer_tokens), 4)


def compute_hallucination(answer: str, chunks: list[dict[str, Any]]) -> float:
    \"\"\"Estimate hallucination likelihood.

    Args:
        answer: LLM-generated answer text.
        chunks: List of enriched chunk dicts.

    Returns:
        Score in [0.0, 1.0] rounded to 4 decimal places.
    \"\"\"
    if chunks:
        return round(1.0 - compute_groundedness(answer, chunks), 4)
    if not answer:
        return 0.0
    words = answer.lower().split()
    if not words:
        return 0.0
    hedge_count = sum(1 for hw in _HEDGE_WORDS if hw in answer.lower())
    return round(min(hedge_count / max(len(words) / 10, 1), 1.0), 4)


def _fetch_spans(trace_id: str) -> list[dict[str, Any]]:
    \"\"\"Fetch all spans for a trace from DynamoDB.

    Args:
        trace_id: Trace identifier to query.

    Returns:
        List of span item dicts.

    Raises:
        Exception: Propagates DynamoDB errors to trigger SQS retry.
    \"\"\"
    resp = trace_tbl.query(KeyConditionExpression=Key("trace_id").eq(trace_id))
    return list(resp.get("Items", []))


def handler(event: dict[str, Any], context: Any) -> None:
    \"\"\"Lambda entry point for SQS scoring queue messages.

    Args:
        event: SQS event with Records list.
        context: Lambda context object.
    \"\"\"
    for record in event.get("Records", []):
        try:
            body = json.loads(record["body"])
            trace_id: str | None = body.get("trace_id")
            if not trace_id:
                logger.warning("Scorer received message without trace_id, skipping")
                continue

            spans = _fetch_spans(trace_id)
            by_type: dict[str, dict[str, Any]] = {s.get("span_type", ""): s for s in spans}

            answer: str = by_type.get("final_response", {}).get("payload", "") or ""
            ret_span = (
                by_type.get("retrieved_chunks") or by_type.get("retriever") or {}
            )
            chunks: list[dict[str, Any]] = ret_span.get("enriched_chunks", [])

            groundedness = compute_groundedness(answer, chunks)
            hallucination = compute_hallucination(answer, chunks)

            total_cost = sum(
                float(s.get("cost_usd") or 0)
                for s in spans
                if s.get("span_type") == "llm_call"
            )
            llm_span = by_type.get("llm_call", {})
            total_tokens = int(llm_span.get("total_tokens") or 0)
            model = llm_span.get("model", "unknown")

            scores_tbl.put_item(Item={
                "trace_id": trace_id,
                "scored_at": datetime.now(timezone.utc).isoformat(),
                "groundedness": str(groundedness),
                "hallucination": str(hallucination),
                "cost_usd": str(round(total_cost, 6)),
                "total_tokens": total_tokens,
                "model": model,
                "chunk_count": len(chunks),
                "answer_len": len(answer),
            })

            cw.put_metric_data(Namespace=NS, MetricData=[
                {"MetricName": "GroundednessScore",  "Value": groundedness,  "Unit": "None"},
                {"MetricName": "HallucinationScore", "Value": hallucination, "Unit": "None"},
                {"MetricName": "ModelCostUSD",       "Value": total_cost,    "Unit": "None"},
            ])

            logger.info(
                "Scored trace %s: groundedness=%.3f hallucination=%.3f cost=$%.4f",
                trace_id, groundedness, hallucination, total_cost,
            )

        except Exception as exc:
            logger.error(
                "ERROR scoring record %s: %s", record.get("messageId", "?"), exc,
                exc_info=True,
            )
            raise
"""

# ---------------------------------------------------------------------------
# cdk_stack/lambda/flagging/flagging.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/flagging/flagging.py"] = """\
\"\"\"
Flagging Lambda handler, DynamoDB Streams consumer on scores_table.

Evaluates four quality rules on every scored trace and creates flag
records when thresholds are breached.  SNS alerts are deduplicated
per rule per batch to prevent alert storms.
\"\"\"

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
    \"\"\"Extract a DynamoDB Streams String or Number attribute as a Python str.

    Streams images use typed dicts: {'S': '...'} or {'N': '...'}.

    Args:
        image: DynamoDB Streams NewImage dict.
        key: Attribute name to extract.
        default: Value to return when attribute is absent.

    Returns:
        String value or default.
    \"\"\"
    attr = image.get(key, {})
    return str(attr.get("S") or attr.get("N") or default)


def _float_attr(image: dict[str, Any], key: str, default: float = 0.0) -> float:
    \"\"\"Extract a DynamoDB Streams attribute as a Python float.

    Args:
        image: DynamoDB Streams NewImage dict.
        key: Attribute name to extract.
        default: Value to return when attribute is absent or unparseable.

    Returns:
        Float value or default.
    \"\"\"
    raw = _str_attr(image, key)
    if not raw:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        logger.warning("Cannot parse attribute %r=%r as float; using default", key, raw)
        return default


def _fetch_spans(trace_id: str) -> dict[str, dict[str, Any]]:
    \"\"\"Fetch all spans for a trace, keyed by span_type.

    Args:
        trace_id: Trace identifier to query.

    Returns:
        Dict mapping span_type to span item.  Empty dict on error.
    \"\"\"
    try:
        resp = trace_tbl.query(KeyConditionExpression=Key("trace_id").eq(trace_id))
        return {s.get("span_type", ""): s for s in resp.get("Items", [])}
    except Exception as exc:
        logger.error("Failed to fetch spans for trace %s: %s", trace_id, exc)
        return {}


def _write_flag(trace_id: str, rule: str, detail: str, severity: str) -> None:
    \"\"\"Persist a flag record and emit a CloudWatch FlaggedAnswers metric.

    Args:
        trace_id: Trace the flag belongs to.
        rule: Rule name that triggered the flag.
        detail: Human-readable description of the violation.
        severity: One of CRITICAL, HIGH, MEDIUM, LOW.
    \"\"\"
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
    \"\"\"Lambda entry point for DynamoDB Streams records.

    Args:
        event: DynamoDB Streams event with Records list.
        context: Lambda context object.
    \"\"\"
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
"""

# ---------------------------------------------------------------------------
# cdk_stack/lambda/feedback/feedback.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/feedback/feedback.py"] = """\
\"\"\"
Feedback Lambda handler for POST /feedback.

Records thumbs-up or thumbs-down user ratings against a completed trace.
A thumbs-down rating automatically creates a USER_THUMBS_DOWN flag.
\"\"\"

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
cw = boto3.client("cloudwatch")
scores_tbl = dynamodb.Table(os.environ["SCORES_TABLE"])
flags_tbl = dynamodb.Table(os.environ["FLAGS_TABLE"])
NS = "AIObservability"

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\\-]{1,128}$")
_VALID_RATINGS: frozenset[str] = frozenset({"thumbs_up", "thumbs_down"})


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    \"\"\"Lambda entry point for POST /feedback.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    \"\"\"
    try:
        body = json.loads(event.get("body") or "{}")
        trace_id = str(body.get("trace_id", ""))
        rating = str(body.get("rating", ""))

        if not _SAFE_ID_RE.match(trace_id):
            return _err(400, "trace_id must be 1-128 alphanumeric/dash/underscore characters")

        if rating not in _VALID_RATINGS:
            return _err(400, "rating must be 'thumbs_up' or 'thumbs_down'")

        now = datetime.now(timezone.utc).isoformat()

        scores_tbl.update_item(
            Key={"trace_id": trace_id},
            UpdateExpression="SET user_rating = :r, feedback_ts = :t",
            ExpressionAttributeValues={":r": rating, ":t": now},
        )

        cw.put_metric_data(
            Namespace=NS,
            MetricData=[{
                "MetricName": "ThumbsDown" if rating == "thumbs_down" else "ThumbsUp",
                "Value": 1,
                "Unit": "Count",
            }],
        )

        if rating == "thumbs_down":
            flags_tbl.put_item(Item={
                "flag_id": str(uuid.uuid4()),
                "trace_id": trace_id,
                "timestamp": now,
                "rule": "USER_THUMBS_DOWN",
                "detail": "User downvoted this response.",
                "severity": "MEDIUM",
                "status": "open",
            })
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
"""

# ---------------------------------------------------------------------------
# cdk_stack/lambda/metrics/metrics.py
# ---------------------------------------------------------------------------
FILES["cdk_stack/lambda/metrics/metrics.py"] = """\
\"\"\"
Metrics Lambda handler, EventBridge scheduled every 5 minutes.

Scans recent LLM call spans with full DynamoDB pagination and emits
aggregate CloudWatch metrics for the operations dashboard.
\"\"\"

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
    \"\"\"Paginated scan for llm_call spans newer than cutoff.

    Args:
        cutoff: ISO-format UTC timestamp lower bound.

    Returns:
        All matching span items across all DynamoDB pages.
    \"\"\"
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
    \"\"\"Lambda entry point for EventBridge scheduled invocations.

    Args:
        event: EventBridge event (contents not used).
        context: Lambda context object.
    \"\"\"
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
"""

# ---------------------------------------------------------------------------
# tests/__init__.py
# ---------------------------------------------------------------------------
FILES["tests/__init__.py"] = ""

# ---------------------------------------------------------------------------
# tests/conftest.py
# ---------------------------------------------------------------------------
FILES["tests/conftest.py"] = """\
\"\"\"Shared pytest fixtures for the LLM observability pipeline test suite.\"\"\"

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def set_lambda_env(monkeypatch: pytest.MonkeyPatch) -> None:
    \"\"\"Inject required Lambda environment variables for all tests.\"\"\"
    monkeypatch.setenv("TRACE_TABLE", "ai-obs-traces")
    monkeypatch.setenv("SCORES_TABLE", "ai-obs-scores")
    monkeypatch.setenv("FLAGS_TABLE", "ai-obs-flags")
    monkeypatch.setenv("ALERT_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:ai-obs-alerts")
    monkeypatch.setenv("SPAN_STREAM", "ai-obs-spans")
    monkeypatch.setenv("SCORING_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/queue")
    monkeypatch.setenv("PROMPT_REGISTRY", "ai-obs-prompts")
"""

# ---------------------------------------------------------------------------
# tests/test_validation.py
# ---------------------------------------------------------------------------
FILES["tests/test_validation.py"] = """\
\"\"\"Tests for src/validation.py: input validation utilities.\"\"\"

from __future__ import annotations

import pytest

from src.validation import (
    validate_environment,
    validate_identifier,
    validate_model,
    validate_or_generate_trace_id,
    validate_prompt_version,
    validate_rating,
    validate_temperature,
)
from src.exceptions import ValidationError


class TestValidateIdentifier:
    \"\"\"validate_identifier: happy path, edge cases, error paths.\"\"\"

    def test_valid_identifier_returns_value(self) -> None:
        # Arrange
        value = "trace-abc_123"
        # Act
        result = validate_identifier(value, "trace_id")
        # Assert
        assert result == value

    def test_max_length_identifier_is_accepted(self) -> None:
        # Arrange
        value = "a" * 128
        # Act / Assert
        assert validate_identifier(value, "field") == value

    def test_too_long_identifier_raises(self) -> None:
        # Arrange
        value = "a" * 129
        # Act / Assert
        with pytest.raises(ValidationError, match="trace_id"):
            validate_identifier(value, "trace_id")

    def test_special_characters_raise(self) -> None:
        # Arrange
        value = "bad!value"
        # Act / Assert
        with pytest.raises(ValidationError):
            validate_identifier(value, "field")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            validate_identifier("", "field")

    def test_non_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            validate_identifier(123, "field")  # type: ignore[arg-type]


class TestValidateOrGenerateTraceId:
    \"\"\"validate_or_generate_trace_id: generates UUID when absent.\"\"\"

    def test_none_generates_uuid(self) -> None:
        result = validate_or_generate_trace_id(None)
        assert len(result) == 36
        assert result.count("-") == 4

    def test_empty_string_generates_uuid(self) -> None:
        result = validate_or_generate_trace_id("")
        assert len(result) == 36

    def test_valid_id_is_returned_unchanged(self) -> None:
        result = validate_or_generate_trace_id("my-trace-id")
        assert result == "my-trace-id"

    def test_invalid_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            validate_or_generate_trace_id("bad id with spaces")


class TestValidateTemperature:
    \"\"\"validate_temperature: numeric range enforcement.\"\"\"

    def test_zero_is_valid(self) -> None:
        assert validate_temperature(0.0) == 0.0

    def test_two_is_valid(self) -> None:
        assert validate_temperature(2.0) == 2.0

    def test_midrange_float_is_valid(self) -> None:
        assert validate_temperature(0.7) == pytest.approx(0.7)

    def test_integer_is_coerced_to_float(self) -> None:
        assert validate_temperature(1) == 1.0

    def test_string_number_is_coerced(self) -> None:
        assert validate_temperature("0.5") == pytest.approx(0.5)

    def test_above_max_raises(self) -> None:
        with pytest.raises(ValidationError, match="temperature"):
            validate_temperature(2.1)

    def test_below_min_raises(self) -> None:
        with pytest.raises(ValidationError, match="temperature"):
            validate_temperature(-0.1)

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValidationError, match="temperature"):
            validate_temperature("hot")


class TestValidateEnvironment:
    \"\"\"validate_environment: only known deployment targets accepted.\"\"\"

    def test_production_is_valid(self) -> None:
        assert validate_environment("production") == "production"

    def test_staging_is_valid(self) -> None:
        assert validate_environment("staging") == "staging"

    def test_unknown_environment_raises(self) -> None:
        with pytest.raises(ValidationError, match="environment"):
            validate_environment("live")


class TestValidateRating:
    \"\"\"validate_rating: only thumbs_up and thumbs_down accepted.\"\"\"

    def test_thumbs_up_is_valid(self) -> None:
        assert validate_rating("thumbs_up") == "thumbs_up"

    def test_thumbs_down_is_valid(self) -> None:
        assert validate_rating("thumbs_down") == "thumbs_down"

    def test_unknown_rating_raises(self) -> None:
        with pytest.raises(ValidationError, match="rating"):
            validate_rating("meh")
"""

# ---------------------------------------------------------------------------
# tests/test_scoring.py
# ---------------------------------------------------------------------------
FILES["tests/test_scoring.py"] = """\
\"\"\"Tests for src/scoring.py: groundedness and hallucination algorithms.\"\"\"

from __future__ import annotations

import pytest

from src.scoring import compute_groundedness, compute_hallucination


class TestComputeGroundedness:
    \"\"\"compute_groundedness: token overlap scoring.\"\"\"

    def test_full_overlap_returns_one(self) -> None:
        # Arrange
        answer = "the capital city of france"
        chunks = [{"text_preview": "the capital city of france is paris"}]
        # Act
        result = compute_groundedness(answer, chunks)
        # Assert
        assert result == pytest.approx(1.0)

    def test_no_overlap_returns_zero(self) -> None:
        answer = "quantum entanglement phenomenon"
        chunks = [{"text_preview": "the cat sat on the mat"}]
        result = compute_groundedness(answer, chunks)
        assert result == 0.0

    def test_empty_answer_returns_zero(self) -> None:
        assert compute_groundedness("", [{"text_preview": "some content"}]) == 0.0

    def test_empty_chunks_returns_zero(self) -> None:
        assert compute_groundedness("some answer", []) == 0.0

    def test_partial_overlap_between_zero_and_one(self) -> None:
        answer = "the sky is blue and clear"
        chunks = [{"text_preview": "the sky appears blue during daytime"}]
        result = compute_groundedness(answer, chunks)
        assert 0.0 < result < 1.0

    def test_result_is_rounded_to_four_places(self) -> None:
        answer = "the quick brown fox"
        chunks = [{"text_preview": "the quick brown fox jumps over"}]
        result = compute_groundedness(answer, chunks)
        assert result == round(result, 4)


class TestComputeHallucination:
    \"\"\"compute_hallucination: inverse groundedness and hedge-word detection.\"\"\"

    def test_with_chunks_is_inverse_of_groundedness(self) -> None:
        answer = "quantum physics explains everything"
        chunks = [{"text_preview": "quantum physics is a branch of science"}]
        g = compute_groundedness(answer, chunks)
        h = compute_hallucination(answer, chunks)
        assert h == pytest.approx(round(1.0 - g, 4))

    def test_no_chunks_empty_answer_returns_zero(self) -> None:
        assert compute_hallucination("", []) == 0.0

    def test_no_chunks_hedge_words_increase_score(self) -> None:
        hedged = "I think it might be probably possibly the case that it seems right"
        no_hedge = "The answer is definitively correct based on the data"
        score_hedged = compute_hallucination(hedged, [])
        score_clean = compute_hallucination(no_hedge, [])
        assert score_hedged > score_clean

    def test_score_capped_at_one(self) -> None:
        very_hedged = " ".join(["i think i believe probably possibly"] * 20)
        result = compute_hallucination(very_hedged, [])
        assert result <= 1.0

    def test_result_is_rounded_to_four_places(self) -> None:
        answer = "some answer text"
        chunks = [{"text_preview": "some source text content"}]
        result = compute_hallucination(answer, chunks)
        assert result == round(result, 4)
"""

# ---------------------------------------------------------------------------
# tests/test_ingest.py
# ---------------------------------------------------------------------------
FILES["tests/test_ingest.py"] = """\
\"\"\"Tests for the ingest Lambda handler.\"\"\"

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _make_event(body: dict[str, Any]) -> dict[str, Any]:
    return {"body": json.dumps(body)}


class TestIngestHandler:
    \"\"\"ingest.handler: happy path, validation errors, and service failures.\"\"\"

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_valid_request_returns_200_with_trace_id(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.ingest.ingest import handler
        mock_table.put_item.return_value = {}
        mock_kinesis.put_record.return_value = {}
        event = _make_event({
            "session_id": "sess-001",
            "model": "claude-sonnet",
            "question": "What is the refund policy?",
        })
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "trace_id" in body
        assert body["status"] == "accepted"

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_provided_trace_id_is_preserved(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.ingest.ingest import handler
        mock_table.put_item.return_value = {}
        mock_kinesis.put_record.return_value = {}
        event = _make_event({"trace_id": "my-trace-123", "question": "hello"})
        # Act
        response = handler(event, None)
        # Assert
        body = json.loads(response["body"])
        assert body["trace_id"] == "my-trace-123"

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_invalid_temperature_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.ingest.ingest import handler
        event = _make_event({"question": "hello", "temperature": 5.0})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400
        assert "temperature" in json.loads(response["body"])["error"]

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_invalid_environment_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.ingest.ingest import handler
        event = _make_event({"question": "hello", "environment": "prod"})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_malformed_json_returns_400(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.ingest.ingest import handler
        event = {"body": "not-json"}
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 400

    @patch("cdk_stack.lambda.ingest.ingest.kinesis")
    @patch("cdk_stack.lambda.ingest.ingest.trace_table")
    def test_dynamodb_failure_returns_500(
        self,
        mock_table: MagicMock,
        mock_kinesis: MagicMock,
    ) -> None:
        # Arrange: mock_table replaces DynamoDB; raising simulates service failure
        from cdk_stack.lambda.ingest.ingest import handler
        mock_table.put_item.side_effect = Exception("DynamoDB error")
        event = _make_event({"question": "hello"})
        # Act
        response = handler(event, None)
        # Assert
        assert response["statusCode"] == 500
"""

# ---------------------------------------------------------------------------
# tests/test_scoring_lambda.py
# ---------------------------------------------------------------------------
FILES["tests/test_scoring_lambda.py"] = """\
\"\"\"Tests for the scorer Lambda handler.\"\"\"

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

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
    \"\"\"scorer.handler: happy path, missing trace_id, and DynamoDB errors.\"\"\"

    @patch("cdk_stack.lambda.scorer.scorer.cw")
    @patch("cdk_stack.lambda.scorer.scorer.scores_tbl")
    @patch("cdk_stack.lambda.scorer.scorer.trace_tbl")
    def test_valid_trace_is_scored_and_persisted(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.scorer.scorer import handler
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

    @patch("cdk_stack.lambda.scorer.scorer.cw")
    @patch("cdk_stack.lambda.scorer.scorer.scores_tbl")
    @patch("cdk_stack.lambda.scorer.scorer.trace_tbl")
    def test_missing_trace_id_is_skipped(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.scorer.scorer import handler
        event = {"Records": [{"messageId": "x", "body": json.dumps({})}]}
        # Act
        handler(event, None)
        # Assert
        mock_trace.query.assert_not_called()
        mock_scores.put_item.assert_not_called()

    @patch("cdk_stack.lambda.scorer.scorer.cw")
    @patch("cdk_stack.lambda.scorer.scorer.scores_tbl")
    @patch("cdk_stack.lambda.scorer.scorer.trace_tbl")
    def test_dynamodb_error_raises_for_sqs_retry(
        self,
        mock_trace: MagicMock,
        mock_scores: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange: raising simulates a DynamoDB failure; SQS should retry
        from cdk_stack.lambda.scorer.scorer import handler
        mock_trace.query.side_effect = Exception("DynamoDB unavailable")
        # Act / Assert
        with pytest.raises(Exception, match="DynamoDB unavailable"):
            handler(_sqs_event("trace-002"), None)
"""

# ---------------------------------------------------------------------------
# tests/test_feedback.py
# ---------------------------------------------------------------------------
FILES["tests/test_feedback.py"] = """\
\"\"\"Tests for the feedback Lambda handler.\"\"\"

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _event(body: dict[str, Any]) -> dict[str, Any]:
    return {"body": json.dumps(body)}


class TestFeedbackHandler:
    \"\"\"feedback.handler: ratings recorded, flags created, validation enforced.\"\"\"

    @patch("cdk_stack.lambda.feedback.feedback.cw")
    @patch("cdk_stack.lambda.feedback.feedback.flags_tbl")
    @patch("cdk_stack.lambda.feedback.feedback.scores_tbl")
    def test_thumbs_up_recorded_no_flag(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.feedback.feedback import handler
        mock_scores.update_item.return_value = {}
        # Act
        response = handler(_event({"trace_id": "trace-001", "rating": "thumbs_up"}), None)
        # Assert
        assert response["statusCode"] == 200
        mock_flags.put_item.assert_not_called()

    @patch("cdk_stack.lambda.feedback.feedback.cw")
    @patch("cdk_stack.lambda.feedback.feedback.flags_tbl")
    @patch("cdk_stack.lambda.feedback.feedback.scores_tbl")
    def test_thumbs_down_creates_flag(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.feedback.feedback import handler
        mock_scores.update_item.return_value = {}
        # Act
        handler(_event({"trace_id": "trace-002", "rating": "thumbs_down"}), None)
        # Assert
        mock_flags.put_item.assert_called_once()
        flag = mock_flags.put_item.call_args[1]["Item"]
        assert flag["rule"] == "USER_THUMBS_DOWN"
        assert flag["trace_id"] == "trace-002"

    @patch("cdk_stack.lambda.feedback.feedback.cw")
    @patch("cdk_stack.lambda.feedback.feedback.flags_tbl")
    @patch("cdk_stack.lambda.feedback.feedback.scores_tbl")
    def test_invalid_rating_returns_400(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.feedback.feedback import handler
        # Act
        response = handler(_event({"trace_id": "trace-003", "rating": "meh"}), None)
        # Assert
        assert response["statusCode"] == 400

    @patch("cdk_stack.lambda.feedback.feedback.cw")
    @patch("cdk_stack.lambda.feedback.feedback.flags_tbl")
    @patch("cdk_stack.lambda.feedback.feedback.scores_tbl")
    def test_invalid_trace_id_returns_400(
        self,
        mock_scores: MagicMock,
        mock_flags: MagicMock,
        mock_cw: MagicMock,
    ) -> None:
        # Arrange
        from cdk_stack.lambda.feedback.feedback import handler
        # Act
        response = handler(
            _event({"trace_id": "bad id with spaces", "rating": "thumbs_up"}), None
        )
        # Assert
        assert response["statusCode"] == 400
"""

# ---------------------------------------------------------------------------
# GitHub Actions CI workflow
# ---------------------------------------------------------------------------
FILES[".github/workflows/ci.yml"] = """\
name: CI

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main, dev]

jobs:
  test:
    name: Lint, type-check, and test
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Lint with Ruff
        run: ruff check src/ cdk_stack/ tests/

      - name: Format check with Black
        run: black --check src/ cdk_stack/ tests/

      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports

      - name: Run tests with coverage
        run: pytest --cov=src --cov-report=term-missing --cov-fail-under=80

  synth:
    name: CDK synth (validate infrastructure)
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Set up Node.js (for CDK CLI)
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Install CDK CLI
        run: npm install -g aws-cdk@latest

      - name: CDK synth
        run: |
          cdk synth \\
            -c alert_email=ci@example.com \\
            -c allowed_origins=https://example.com
        env:
          AWS_DEFAULT_REGION: us-east-1
          AWS_ACCESS_KEY_ID: dummy
          AWS_SECRET_ACCESS_KEY: dummy
"""

# ---------------------------------------------------------------------------
# docs/specs stubs
# ---------------------------------------------------------------------------
FILES["docs/specs/00_system_overview.md"] = """\
# 00 System Overview

## Purpose
Production-grade observability pipeline for LLM applications deployed on AWS.
Captures every trace, scores quality, flags violations, and surfaces metrics
to operators in real time.

## Code Conventions
- Python 3.12, Black formatter, Ruff linter, mypy strict mode
- All functions fully type-annotated
- No print() in production code; use logging module with getLogger(__name__)
- Config via pydantic BaseSettings, no inline os.getenv()
- Custom exceptions in src/exceptions.py
- Tests: pytest, AAA structure, >80% coverage

## Components
- API Gateway: POST /traces, POST /feedback
- IngestFn: validates, stores span-0, fans out to Kinesis
- ProcessorFn: enriches spans, calculates cost, queues final responses
- ScorerFn: groundedness + hallucination scoring
- FlaggingFn: rule-based quality enforcement
- FeedbackFn: user rating capture
- MetricsFn: scheduled CloudWatch metric aggregation
"""

FILES["docs/specs/01_architecture.md"] = """\
# 01 Architecture

See docs/architecture.md for the full data flow diagram.

## Key design decisions
- Six per-function IAM roles (least privilege)
- KMS CMKs for all storage (DynamoDB, S3, SQS, SNS, Kinesis)
- SQS DLQ with CloudWatch alarm for poison message detection
- Kinesis 7-day retention to survive weekend outages
- WAFv2 with OWASP managed rules on API Gateway
- CORS locked to explicit origin list, no wildcard
"""

FILES["docs/specs/02_data_model.md"] = """\
# 02 Data Model

## DynamoDB Tables

### ai-obs-traces
PK: trace_id (String), SK: span_id (String)
GSI: session-index (PK: session_id, SK: timestamp)
TTL: ttl attribute (90 days)
Streams: NEW_AND_OLD_IMAGES

### ai-obs-scores
PK: trace_id (String)
Streams: NEW_AND_OLD_IMAGES (triggers FlaggingFn)

### ai-obs-flags
PK: flag_id (String), SK: trace_id (String)

### ai-obs-prompts
PK: prompt_id (String), SK: version (String)

## Python data models
See src/models.py for Span, QualityScore, Flag, IngestRequest, ScoringMessage.
"""

FILES["docs/specs/03_workflows_and_api.md"] = """\
# 03 Workflows and API

## POST /traces
Auth: x-api-key header required
Request: { session_id, model, prompt_version, temperature, environment, question, trace_id? }
Response 200: { trace_id, status: "accepted" }
Response 400: { error: "<validation message>" }

## POST /feedback
Auth: x-api-key header required
Request: { trace_id, rating: "thumbs_up" | "thumbs_down" }
Response 200: { status: "recorded" }
Response 400: { error: "<validation message>" }
"""

FILES["docs/specs/04_implementation_plan.md"] = """\
# 04 Implementation Plan

- [x] Bootstrap: pyproject.toml, ruff, black, mypy, pre-commit
- [x] src/config.py: pydantic BaseSettings
- [x] src/models.py: domain dataclasses
- [x] src/exceptions.py: custom exception hierarchy
- [x] src/validation.py: input validation utilities
- [x] src/scoring.py: groundedness and hallucination algorithms
- [x] Lambda handlers (6): ingest, processor, scorer, flagging, feedback, metrics
- [x] CDK stack: refactored into private methods, per-function IAM roles
- [x] Tests: validation, scoring, ingest, scorer, feedback
- [x] GitHub Actions CI: lint, type-check, test, cdk synth
- [ ] Embedding-based scorer upgrade (see docs/scorer_upgrade.md)
- [ ] VPC endpoints for Lambda-to-AWS service traffic
- [ ] GET /traces query endpoint
"""

FILES["docs/specs/05_local_development.md"] = """\
# 05 Local Development

```bash
# 1. Install Python 3.12 (Microsoft Store on Windows)
python3.12 -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Run tests
pytest

# 4. Lint and format
ruff check src/ cdk_stack/ tests/
black src/ cdk_stack/ tests/

# 5. CDK synth (validates infra without deploying)
cdk synth -c alert_email=you@example.com -c allowed_origins=https://localhost:3000

# 6. Deploy
cdk deploy -c alert_email=you@example.com -c allowed_origins=https://your-app.example.com
```
"""

FILES["docs/specs/06_result_schemas.md"] = """\
# 06 Result Schemas

## QualityScore record (ai-obs-scores)
{
  trace_id: string,
  scored_at: ISO timestamp,
  groundedness: string (float 0-1),
  hallucination: string (float 0-1),
  cost_usd: string (decimal),
  total_tokens: number,
  model: string,
  chunk_count: number,
  answer_len: number
}

## Flag record (ai-obs-flags)
{
  flag_id: UUID string,
  trace_id: string,
  timestamp: ISO timestamp,
  rule: string,
  detail: string,
  severity: CRITICAL | HIGH | MEDIUM | LOW,
  status: open | closed
}
"""

FILES["docs/specs/07_cloud_deployment.md"] = """\
# 07 Cloud Deployment

## Prerequisites
- Python 3.12 (Microsoft Store on Windows)
- Node.js 20+ (for CDK CLI)
- AWS credentials configured (aws configure)
- CDK CLI: npm install -g aws-cdk@latest

## First deploy
```bash
cdk bootstrap aws://<account>/<region>
cdk deploy -c alert_email=ops@example.com -c allowed_origins=https://your-app.example.com
```

## Outputs
- ApiEndpoint: live API URL
- AlertTopicArn: SNS topic (confirm email subscription)
- ScoringDLQUrl: watch for poison messages
- DashboardUrl: CloudWatch operations dashboard

## Tear down
```bash
cdk destroy -c alert_email=ops@example.com -c allowed_origins=https://your-app.example.com
```

Note: S3 bucket and KMS keys have RemovalPolicy.RETAIN, delete manually if needed.
"""


# ---------------------------------------------------------------------------
# Write all files
# ---------------------------------------------------------------------------
print(f"Writing {len(FILES)} files to {ROOT}...")
print()

for path, content in FILES.items():
    write(path, content)

print()
print(f"Done. {len(FILES)} files written.")
print()
print("Next steps:")
print("  python3.12 -m venv .venv")
print("  source .venv/Scripts/activate")
print("  pip install -r requirements-dev.txt")
print("  pytest")
print("  cdk synth -c alert_email=you@example.com -c allowed_origins=https://example.com")
