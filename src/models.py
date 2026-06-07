"""
Shared domain data models.

All structured data crossing function boundaries uses these types.
No raw dicts passed between modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass
class Span:
    """A single unit of observability data emitted by an LLM pipeline step.

    Spans are the atomic unit of the pipeline.  Every LLM call, retriever
    invocation, and user question produces exactly one span.
    """

    trace_id: str
    span_id: str
    span_type: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
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
    """Quality scores computed by the scorer for a completed trace."""

    trace_id: str
    groundedness: float
    hallucination: float
    cost_usd: Decimal
    total_tokens: int
    model: str
    chunk_count: int
    answer_len: int
    scored_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def __repr__(self) -> str:
        return (
            f"QualityScore(trace_id={self.trace_id!r}, "
            f"groundedness={self.groundedness:.3f}, "
            f"hallucination={self.hallucination:.3f})"
        )


@dataclass
class Flag:
    """A quality or policy violation flag raised by the flagging engine."""

    flag_id: str
    trace_id: str
    rule: str
    detail: str
    severity: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
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
    """Validated ingest payload from the API Gateway POST /traces body."""

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
    """Message placed on the SQS scoring queue by the processor."""

    trace_id: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to SQS message body dict."""
        return {"trace_id": self.trace_id}

    def __repr__(self) -> str:
        return f"ScoringMessage(trace_id={self.trace_id!r})"
