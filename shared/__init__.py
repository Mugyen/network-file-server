"""Shared helpers used across server, relay, and agent packages.

Public API re-exports — importers may use either:
    from shared import parse_duration, compute_backoff, repo_root
    from shared.duration import parse_duration
"""

from shared.backoff import compute_backoff
from shared.duration import parse_duration
from shared.network import detect_all_lan_ips, detect_primary_lan_ip
from shared.paths import repo_root
from shared.qr import generate_ascii_qr, generate_svg_qr
from shared.spa import SPA_PLACEHOLDER_HTML, spa_shell_response

__all__ = [
    "SPA_PLACEHOLDER_HTML",
    "compute_backoff",
    "detect_all_lan_ips",
    "detect_primary_lan_ip",
    "generate_ascii_qr",
    "generate_svg_qr",
    "parse_duration",
    "repo_root",
    "spa_shell_response",
]
