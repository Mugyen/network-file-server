"""Exponential backoff with jitter for reconnect loops."""

import random


def compute_backoff(attempt: int, base: float, cap: float, jitter_factor: float) -> float:
    """Compute an exponential backoff delay with optional jitter."""
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    if base <= 0:
        raise ValueError(f"base must be > 0, got {base}")
    if cap < base:
        raise ValueError(f"cap must be >= base ({base}), got {cap}")
    if not 0.0 <= jitter_factor <= 1.0:
        raise ValueError(f"jitter_factor must be in [0, 1], got {jitter_factor}")

    # int ** int is typed Any in typeshed; the explicit annotation keeps this float.
    exp_delay: float = min(base * (2 ** (attempt - 1)), cap)
    jitter = random.uniform(-jitter_factor, jitter_factor) * exp_delay
    return max(0.0, exp_delay + jitter)
