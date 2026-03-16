"""Tests for agent/duration.py parse_duration function."""

import pytest

from agent.duration import parse_duration


class TestParseDuration:
    """Tests for parse_duration — converts human-readable duration strings to seconds."""

    def test_seconds(self) -> None:
        """parse_duration('90s') returns 90."""
        assert parse_duration("90s") == 90

    def test_minutes(self) -> None:
        """parse_duration('30m') returns 1800."""
        assert parse_duration("30m") == 1800

    def test_hours(self) -> None:
        """parse_duration('2h') returns 7200."""
        assert parse_duration("2h") == 7200

    def test_days(self) -> None:
        """parse_duration('1d') returns 86400."""
        assert parse_duration("1d") == 86400

    def test_single_second(self) -> None:
        """parse_duration('1s') returns 1."""
        assert parse_duration("1s") == 1

    def test_large_minutes(self) -> None:
        """parse_duration('120m') returns 7200."""
        assert parse_duration("120m") == 7200

    def test_invalid_unit_raises_value_error(self) -> None:
        """parse_duration('30x') raises ValueError for unknown unit."""
        with pytest.raises(ValueError):
            parse_duration("30x")

    def test_non_numeric_raises_value_error(self) -> None:
        """parse_duration('abc') raises ValueError for non-numeric input."""
        with pytest.raises(ValueError):
            parse_duration("abc")

    def test_empty_string_raises_value_error(self) -> None:
        """parse_duration('') raises ValueError for empty string."""
        with pytest.raises(ValueError):
            parse_duration("")

    def test_no_unit_raises_value_error(self) -> None:
        """parse_duration('30') raises ValueError when unit is missing."""
        with pytest.raises(ValueError):
            parse_duration("30")

    def test_only_unit_raises_value_error(self) -> None:
        """parse_duration('m') raises ValueError when number is missing."""
        with pytest.raises(ValueError):
            parse_duration("m")

    def test_error_message_is_descriptive(self) -> None:
        """parse_duration raises ValueError with a descriptive message on bad input."""
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("bad")
