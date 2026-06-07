"""
Input validation utilities used by the ingest and feedback handlers.

All validation logic lives here so it can be unit-tested independently
of Lambda plumbing.
"""

from __future__ import annotations

import re
import uuid

from src.exceptions import ValidationError

_SAFE_ID_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_SAFE_MODEL_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-\.]{1,64}$")
_SAFE_VER_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z0-9_\-\.]{1,32}$")
_VALID_ENVIRONMENTS: frozenset[str] = frozenset({"production", "staging", "development", "test"})
_VALID_RATINGS: frozenset[str] = frozenset({"thumbs_up", "thumbs_down"})
_TEMP_MIN: float = 0.0
_TEMP_MAX: float = 2.0


def validate_identifier(value: str, field: str) -> str:
    """Validate that value is a safe alphanumeric identifier.

    Args:
        value: The string to validate.
        field: Field name used in the error message.

    Returns:
        The validated value unchanged.

    Raises:
        ValidationError: If value does not match the safe identifier pattern.
    """
    if not isinstance(value, str) or not _SAFE_ID_RE.match(value):
        raise ValidationError(
            field,
            "must be 1-128 characters: letters, digits, hyphens, underscores only",
        )
    return value


def validate_or_generate_trace_id(raw: str | None) -> str:
    """Return raw validated, or generate a new UUID if raw is falsy.

    Args:
        raw: Caller-supplied trace_id or None.

    Returns:
        A validated trace_id string.

    Raises:
        ValidationError: If raw is provided but fails identifier validation.
    """
    if not raw:
        return str(uuid.uuid4())
    return validate_identifier(raw, "trace_id")


def validate_model(value: str) -> str:
    """Validate model identifier format.

    Args:
        value: Model name string to validate.

    Returns:
        The validated model name.

    Raises:
        ValidationError: If the model name contains invalid characters.
    """
    if not isinstance(value, str) or not _SAFE_MODEL_RE.match(value):
        raise ValidationError("model", "must be 1-64 alphanumeric/dash/dot characters")
    return value


def validate_prompt_version(value: str) -> str:
    """Validate prompt version string format.

    Args:
        value: Prompt version string to validate.

    Returns:
        The validated version string.

    Raises:
        ValidationError: If the version contains invalid characters.
    """
    if not isinstance(value, str) or not _SAFE_VER_RE.match(value):
        raise ValidationError("prompt_version", "must be 1-32 alphanumeric/dash/dot characters")
    return value


def validate_environment(value: str) -> str:
    """Validate that environment is a recognised deployment target.

    Args:
        value: Environment string to validate.

    Returns:
        The validated environment string.

    Raises:
        ValidationError: If value is not in the allowed set.
    """
    if value not in _VALID_ENVIRONMENTS:
        allowed = ", ".join(sorted(_VALID_ENVIRONMENTS))
        raise ValidationError("environment", f"must be one of: {allowed}")
    return value


def validate_temperature(value: float | int | str) -> float:
    """Validate that temperature is a float in [0.0, 2.0].

    Args:
        value: Raw temperature value from caller.

    Returns:
        Validated float temperature.

    Raises:
        ValidationError: If value cannot be cast to float or is out of range.
    """
    try:
        temp = float(value)
    except (TypeError, ValueError):
        raise ValidationError("temperature", f"must be a number, got {value!r}") from None
    if not (_TEMP_MIN <= temp <= _TEMP_MAX):
        raise ValidationError(
            "temperature", f"must be between {_TEMP_MIN} and {_TEMP_MAX}, got {temp}"
        )
    return temp


def validate_rating(value: str) -> str:
    """Validate that a feedback rating is one of the accepted values.

    Args:
        value: Rating string from caller.

    Returns:
        The validated rating string.

    Raises:
        ValidationError: If value is not a recognised rating.
    """
    if value not in _VALID_RATINGS:
        raise ValidationError("rating", "must be 'thumbs_up' or 'thumbs_down'")
    return value
