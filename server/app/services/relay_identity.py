"""Trusted relay-injected identity headers.

The relay strips any inbound ``X-WFS-*`` headers and injects authoritative
ones for allowlisted users. The server only honours these headers when it
is relay-served (``mount_code`` set) — in pure LAN mode the headers are
ignored entirely, since a LAN client could otherwise spoof them.

All functions take the app's ServerConfig explicitly so trust decisions
are per-app, never process-global.
"""

from collections.abc import Mapping

from accounts import Role
from server.app.config import ServerConfig

HEADER_USER = "x-wfs-user"
HEADER_ROLE = "x-wfs-role"
HEADER_AUTH_BYPASS = "x-wfs-auth-bypass"


def is_relay_served(config: ServerConfig) -> bool:
    """True if this server is served through the relay (a mount)."""
    return config.mount_code is not None


def trusted_role(config: ServerConfig, headers: Mapping[str, str]) -> Role | None:
    """Return the relay-asserted role, or None if absent/untrusted/invalid."""
    if not is_relay_served(config):
        return None
    raw = headers.get(HEADER_ROLE)
    if raw is None:
        return None
    try:
        return Role(raw)
    except ValueError:
        return None


def trusted_user(config: ServerConfig, headers: Mapping[str, str]) -> str | None:
    """Return the relay-asserted username, or None if absent/untrusted."""
    if not is_relay_served(config):
        return None
    return headers.get(HEADER_USER)


def is_auth_bypassed(config: ServerConfig, headers: Mapping[str, str]) -> bool:
    """True if the relay vouched for an allowlisted user (skip password)."""
    if not is_relay_served(config):
        return False
    return headers.get(HEADER_AUTH_BYPASS) == "1"
