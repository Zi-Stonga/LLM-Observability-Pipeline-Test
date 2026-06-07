"""
Quality scoring logic: groundedness and hallucination estimation.

These functions contain the pure scoring algorithms with no I/O side effects.
Replace _groundedness and _hallucination with embedding-based or LLM-judge
implementations without touching any handler code.
"""

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

_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"\b[a-z]{3,}\b")


def _tokenize(text: str) -> set[str]:
    """Return a lowercase word-token set for semantic overlap estimation.

    Args:
        text: Input text to tokenize.

    Returns:
        Set of lowercase word tokens (3+ characters).
    """
    return set(_TOKEN_PATTERN.findall(text.lower()))


def compute_groundedness(answer: str, chunks: list[dict[str, str]]) -> float:
    """Compute normalised token overlap between answer and source chunks.

    A score of 1.0 means every content word in the answer appeared in the
    source material.  0.0 means no overlap at all.

    Args:
        answer: The LLM-generated answer text.
        chunks: List of enriched retriever chunk dicts with 'text_preview' keys.

    Returns:
        Groundedness score in [0.0, 1.0], rounded to 4 decimal places.
    """
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
    """Estimate hallucination likelihood as a score in [0.0, 1.0].

    When source chunks are present: 1 - groundedness.
    When no source chunks exist: hedge-word density as a fabrication signal.

    Args:
        answer: The LLM-generated answer text.
        chunks: List of enriched retriever chunk dicts.

    Returns:
        Hallucination score in [0.0, 1.0], rounded to 4 decimal places.
    """
    if chunks:
        return round(1.0 - compute_groundedness(answer, chunks), 4)

    if not answer:
        return 0.0

    words = answer.lower().split()
    if not words:
        return 0.0

    hedge_count = sum(1 for hw in _HEDGE_WORDS if hw in answer.lower())
    return round(min(hedge_count / max(len(words) / 10, 1), 1.0), 4)
