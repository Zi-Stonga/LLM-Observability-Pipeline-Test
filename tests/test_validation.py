"""Tests for src/validation.py: input validation utilities."""

from __future__ import annotations

import pytest

from src.exceptions import ValidationError
from src.validation import (
    validate_environment,
    validate_identifier,
    validate_or_generate_trace_id,
    validate_rating,
    validate_temperature,
)


class TestValidateIdentifier:
    """validate_identifier: happy path, edge cases, error paths."""

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
    """validate_or_generate_trace_id: generates UUID when absent."""

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
    """validate_temperature: numeric range enforcement."""

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
    """validate_environment: only known deployment targets accepted."""

    def test_production_is_valid(self) -> None:
        assert validate_environment("production") == "production"

    def test_staging_is_valid(self) -> None:
        assert validate_environment("staging") == "staging"

    def test_unknown_environment_raises(self) -> None:
        with pytest.raises(ValidationError, match="environment"):
            validate_environment("live")


class TestValidateRating:
    """validate_rating: only thumbs_up and thumbs_down accepted."""

    def test_thumbs_up_is_valid(self) -> None:
        assert validate_rating("thumbs_up") == "thumbs_up"

    def test_thumbs_down_is_valid(self) -> None:
        assert validate_rating("thumbs_down") == "thumbs_down"

    def test_unknown_rating_raises(self) -> None:
        with pytest.raises(ValidationError, match="rating"):
            validate_rating("meh")
