"""Trusted relay-injected identity headers.

The relay strips any inbound ``X-WFS-*`` headers and injects authoritative
ones for allowlisted users. The server only honours these headers when it
is relay-served (``mount_code`` set) — in pure LAN mode the headers are
ignored entirely, since a LAN client could otherwise spoof them.
"""

from collections.abc import Mapping

from accounts import Role
from server.app.config import get_server_config

HEADER_USER = "x-wfs-user"
HEADER_ROLE = "x-wfs-role"
HEADER_AUTH_BYPASS = "x-wfs-auth-bypass"


def is_relay_served() -> bool:
    """True if this server is served through the relay (a mount)."""
    try:
        return get_server_config().mount_code is not None
    except RuntimeError:
        # Config not initialised — do not trust headers.
        return False


def trusted_role(headers: Mapping[str, str]) -> Role | None:
    """Return the relay-asserted role, or None if absent/untrusted/invalid."""
    if not is_relay_served():
        return None
    raw = headers.get(HEADER_ROLE)
    if raw is None:
        return None
    try:
        return Role(raw)
    except ValueError:
        return None


def trusted_user(headers: Mapping[str, str]) -> str | None:
    """Return the relay-asserted username, or None if absent/untrusted."""
    if not is_relay_served():
        return None
    return headers.get(HEADER_USER)


def is_auth_bypassed(headers: Mapping[str, str]) -> bool:
    """True if the relay vouched for an allowlisted user (skip password)."""
    if not is_relay_served():
        return False
    return headers.get(HEADER_AUTH_BYPASS) == "1"
