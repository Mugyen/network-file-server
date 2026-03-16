"""Tests for compute_backoff — exponential backoff with jitter."""

import math

import pytest


def test_compute_backoff_attempt_1_near_base() -> None:
    """compute_backoff(1, 1.0, 60.0, 0.5) returns a value near 1.0 (base)."""
    from agent.backoff import compute_backoff
    result = compute_backoff(attempt=1, base=1.0, cap=60.0, jitter_factor=0.5)
    # With 50% jitter on base 1.0: range is [0.5, 1.5]
    assert 0.0 <= result <= 2.0


def test_compute_backoff_high_attempt_respects_cap() -> None:
    """compute_backoff(7, 1.0, 60.0, 0.5) returns value near 60.0 (cap reached)."""
    from agent.backoff import compute_backoff
    # attempt=7: 1.0 * 2^6 = 64 > 60, so exp_delay = 60.0
    result = compute_backoff(attempt=7, base=1.0, cap=60.0, jitter_factor=0.5)
    # With 50% jitter: max jitter is 30.0, but result should be around 60
    assert result >= 30.0  # at minimum half the cap with max negative jitter
    assert result <= 90.0  # at most cap + 50% jitter


def test_compute_backoff_no_jitter_returns_exact_exponential() -> None:
    """compute_backoff with jitter_factor=0 returns exact exponential value."""
    from agent.backoff import compute_backoff
    result = compute_backoff(attempt=3, base=2.0, cap=60.0, jitter_factor=0.0)
    # attempt=3: 2.0 * 2^2 = 8.0
    assert result == pytest.approx(8.0)


def test_compute_backoff_no_jitter_caps_at_cap() -> None:
    """compute_backoff with jitter_factor=0 caps at cap value."""
    from agent.backoff import compute_backoff
    result = compute_backoff(attempt=10, base=1.0, cap=60.0, jitter_factor=0.0)
    assert result == pytest.approx(60.0)


def test_compute_backoff_attempt_below_1_raises_value_error() -> None:
    """attempt < 1 raises ValueError."""
    from agent.backoff import compute_backoff
    with pytest.raises(ValueError, match="attempt"):
        compute_backoff(attempt=0, base=1.0, cap=60.0, jitter_factor=0.0)


def test_compute_backoff_base_zero_raises_value_error() -> None:
    """base <= 0 raises ValueError."""
    from agent.backoff import compute_backoff
    with pytest.raises(ValueError, match="base"):
        compute_backoff(attempt=1, base=0.0, cap=60.0, jitter_factor=0.0)


def test_compute_backoff_cap_below_base_raises_value_error() -> None:
    """cap < base raises ValueError."""
    from agent.backoff import compute_backoff
    with pytest.raises(ValueError, match="cap"):
        compute_backoff(attempt=1, base=10.0, cap=5.0, jitter_factor=0.0)


def test_compute_backoff_jitter_below_0_raises_value_error() -> None:
    """jitter_factor < 0 raises ValueError."""
    from agent.backoff import compute_backoff
    with pytest.raises(ValueError, match="jitter"):
        compute_backoff(attempt=1, base=1.0, cap=60.0, jitter_factor=-0.1)


def test_compute_backoff_jitter_above_1_raises_value_error() -> None:
    """jitter_factor > 1 raises ValueError."""
    from agent.backoff import compute_backoff
    with pytest.raises(ValueError, match="jitter"):
        compute_backoff(attempt=1, base=1.0, cap=60.0, jitter_factor=1.1)


def test_compute_backoff_result_is_always_non_negative() -> None:
    """Result is always >= 0 for valid inputs."""
    from agent.backoff import compute_backoff
    for attempt in range(1, 10):
        result = compute_backoff(attempt=attempt, base=1.0, cap=60.0, jitter_factor=1.0)
        assert result >= 0.0


def test_compute_backoff_attempt_2_doubles_base() -> None:
    """compute_backoff(2, 1.0, 60.0, 0) returns exactly 2.0 (base * 2^1)."""
    from agent.backoff import compute_backoff
    result = compute_backoff(attempt=2, base=1.0, cap=60.0, jitter_factor=0.0)
    assert result == pytest.approx(2.0)
