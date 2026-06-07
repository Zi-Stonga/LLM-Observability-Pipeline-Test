"""Tests for src/scoring.py: groundedness and hallucination algorithms."""

from __future__ import annotations

import pytest

from src.scoring import compute_groundedness, compute_hallucination


class TestComputeGroundedness:
    """compute_groundedness: token overlap scoring."""

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
    """compute_hallucination: inverse groundedness and hedge-word detection."""

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
