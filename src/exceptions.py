"""
Domain exception hierarchy.

All internal errors inherit from PipelineError so callers can catch
the base type or specific subtypes as needed.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base exception for all LLM observability pipeline errors."""


class ValidationError(PipelineError):
    """Raised when inbound request data fails validation.

    Includes the field name and a human-readable reason so callers
    can return a useful 400 response without leaking internals.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Validation failed for {field!r}: {reason}")


class StorageError(PipelineError):
    """Raised when a DynamoDB read or write operation fails."""


class StreamError(PipelineError):
    """Raised when a Kinesis put_record call fails."""


class ScoringError(PipelineError):
    """Raised when span scoring cannot be completed."""


class FlaggingError(PipelineError):
    """Raised when the flagging engine encounters an unrecoverable error."""
