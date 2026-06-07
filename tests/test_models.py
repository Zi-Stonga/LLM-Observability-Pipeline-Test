"""Tests for src/models.py: domain dataclasses."""

from __future__ import annotations

from decimal import Decimal

from src.models import Flag, IngestRequest, QualityScore, ScoringMessage, Span


class TestSpan:
    """Span dataclass: construction and repr."""

    def test_defaults_are_set(self) -> None:
        span = Span(trace_id="t1", span_id="s1", span_type="user_question")
        assert span.session_id == "unknown"
        assert span.status == "captured"
        assert span.payload == ""

    def test_repr_contains_key_fields(self) -> None:
        span = Span(trace_id="t1", span_id="s1", span_type="llm_call")
        assert "t1" in repr(span)
        assert "llm_call" in repr(span)

    def test_timestamp_is_populated(self) -> None:
        span = Span(trace_id="t1", span_id="s1", span_type="llm_call")
        assert span.timestamp != ""


class TestQualityScore:
    """QualityScore dataclass: construction and repr."""

    def test_fields_are_stored(self) -> None:
        score = QualityScore(
            trace_id="t1",
            groundedness=0.9,
            hallucination=0.1,
            cost_usd=Decimal("0.001"),
            total_tokens=100,
            model="claude-sonnet",
            chunk_count=3,
            answer_len=200,
        )
        assert score.groundedness == 0.9
        assert score.hallucination == 0.1
        assert score.total_tokens == 100

    def test_repr_contains_scores(self) -> None:
        score = QualityScore(
            trace_id="t1",
            groundedness=0.9,
            hallucination=0.1,
            cost_usd=Decimal("0.001"),
            total_tokens=100,
            model="claude-sonnet",
            chunk_count=3,
            answer_len=200,
        )
        assert "0.900" in repr(score)
        assert "t1" in repr(score)


class TestFlag:
    """Flag dataclass: construction and repr."""

    def test_defaults_are_set(self) -> None:
        flag = Flag(
            flag_id="f1",
            trace_id="t1",
            rule="HIGH_HALLUCINATION",
            detail="test detail",
            severity="CRITICAL",
        )
        assert flag.status == "open"

    def test_repr_contains_rule(self) -> None:
        flag = Flag(
            flag_id="f1",
            trace_id="t1",
            rule="COST_SPIKE",
            detail="detail",
            severity="MEDIUM",
        )
        assert "COST_SPIKE" in repr(flag)


class TestIngestRequest:
    """IngestRequest dataclass: defaults and repr."""

    def test_defaults_are_set(self) -> None:
        req = IngestRequest(question="What is the policy?")
        assert req.session_id == "unknown"
        assert req.temperature == 0.7
        assert req.environment == "production"

    def test_repr_shows_session_and_model(self) -> None:
        req = IngestRequest(question="hello", session_id="s1", model="gpt-4")
        assert "s1" in repr(req)
        assert "gpt-4" in repr(req)


class TestScoringMessage:
    """ScoringMessage: serialization."""

    def test_to_dict_contains_trace_id(self) -> None:
        msg = ScoringMessage(trace_id="t1")
        assert msg.to_dict() == {"trace_id": "t1"}

    def test_repr_contains_trace_id(self) -> None:
        msg = ScoringMessage(trace_id="t1")
        assert "t1" in repr(msg)
