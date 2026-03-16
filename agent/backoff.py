"""Exponential backoff with jitter for WebSocket reconnection.

Provides a pure function for computing retry delays that avoids thundering-herd
problems through random jitter.
"""

import random


def compute_backoff(attempt: int, base: float, cap: float, jitter_factor: float) -> float:
    """Compute an exponential backoff delay with optional jitter.

    Formula:
        exp_delay = min(base * 2^(attempt - 1), cap)
        jitter    = random.uniform(-jitter_factor, jitter_factor) * exp_delay
        result    = max(0.0, exp_delay + jitter)

    Args:
        attempt:       Reconnect attempt number, 1-based. Must be >= 1.
        base:          Initial delay in seconds for attempt=1. Must be > 0.
        cap:           Maximum delay in seconds. Must be >= base.
        jitter_factor: Fraction of exp_delay to use as random jitter.
                       0.0 = no jitter (deterministic). Must be in [0, 1].

    Returns:
        Computed delay in seconds, always >= 0.

    Raises:
        ValueError: If attempt < 1, base <= 0, cap < base, or
                    jitter_factor outside [0, 1].
    """
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    if base <= 0:
        raise ValueError(f"base must be > 0, got {base}")
    if cap < base:
        raise ValueError(f"cap must be >= base ({base}), got {cap}")
    if not 0.0 <= jitter_factor <= 1.0:
        raise ValueError(f"jitter_factor must be in [0, 1], got {jitter_factor}")

    exp_delay = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(-jitter_factor, jitter_factor) * exp_delay
    return max(0.0, exp_delay + jitter)
