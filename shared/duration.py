"""Duration string parser for TTL-style CLI arguments."""

import re

_PATTERN = re.compile(r"^(\d+)([smhd])$")

_UNITS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_duration(value: str) -> int:
    """Parse a human-readable duration string into seconds."""
    match = _PATTERN.match(value)
    if match is None:
        raise ValueError(
            f"Invalid duration {value!r}. Expected format: <number><unit> where unit is one of s, m, h, d (e.g. '30m', '2h')."
        )
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * _UNITS[unit]
