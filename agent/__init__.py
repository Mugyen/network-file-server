"""Agent package — CLI tooling for mounting local directories through a relay server."""

from shared.backoff import compute_backoff
from shared.duration import parse_duration


def run_mount(*args, **kwargs):
    """Lazy proxy to the CLI entry point to avoid import-time side effects."""
    from agent.cli import run_mount as _run_mount

    return _run_mount(*args, **kwargs)


__all__ = ["compute_backoff", "parse_duration", "run_mount"]
