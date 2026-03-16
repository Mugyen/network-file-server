"""Duration string parser for TTL arguments.

Converts human-readable duration strings (e.g. '30m', '2h', '1d') to seconds.
"""

import re

_PATTERN = re.compile(r"^(\d+)([smhd])$")

_UNITS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


def parse_duration(value: str) -> int:
    """Parse a human-readable duration string into seconds.

    Accepted format: a positive integer followed by a unit character.
    Supported units: s (seconds), m (minutes), h (hours), d (days).

    Args:
        value: Duration string such as '30m', '2h', '1d', or '90s'.

    Returns:
        The duration in seconds as an integer.

    Raises:
        ValueError: If the string does not match the expected format or uses an
                    unknown unit.
    """
    match = _PATTERN.match(value)
    if match is None:
        raise ValueError(
            f"Invalid duration {value!r}. Expected format: <number><unit> where unit is one of s, m, h, d (e.g. '30m', '2h')."
        )
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * _UNITS[unit]
