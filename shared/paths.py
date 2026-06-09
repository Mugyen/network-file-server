"""Repository path helpers."""

from pathlib import Path


def repo_root() -> Path:
    """Return the repository root derived from this module's location."""
    return Path(__file__).resolve().parent.parent
