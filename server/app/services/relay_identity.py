"""Trusted relay-injected identity headers (HMAC-verified).

The relay strips any inbound ``X-WFS-*`` headers and injects authoritative
ones for allowlisted users, signed with a per-mount secret
(``shared.identity_sig``). The server honours these headers only when ALL of:

1. it is relay-served (``mount_code`` set), and
2. it has the per-mount secret (``identity_secret`` — set by the agent for
   tunnel-served mounts; ``None`` for LAN mode and local mounts), and
3. the ``X-WFS-Identity-Sig`` header is a valid HMAC over the exact
   (user, role, auth-bypass) tuple presented.

This closes the spoofing vector where a client reaches the agent's local
server port directly (e.g. on the LAN, bypassing the tunnel) and forges
identity headers: without the secret it cannot produce a valid signature.

All functions take the app's ServerConfig explicitly so trust decisions are
per-app, never process-global.
"""

from collections.abc import Mapping

from accounts import Role
from server.app.config import ServerConfig
from shared.identity_sig import IDENTITY_SIG_HEADER, verify_identity

HEADER_USER = "x-wfs-user"
HEADER_ROLE = "x-wfs-role"
HEADER_AUTH_BYPASS = "x-wfs-auth-bypass"


def is_relay_served(config: ServerConfig) -> bool:
    """True if this server is served through the relay (a mount)."""
    return config.mount_code is not None


def _verified_identity(
    config: ServerConfig, headers: Mapping[str, str]
) -> tuple[str, str, bool] | None:
    """Return the verified (user, role, bypass) tuple, or None if untrusted.

    Returns None unless the server is relay-served, holds the per-mount
    secret, and the presented headers carry a valid signature over exactly
    this (user, role, bypass) tuple. A missing/forged signature, a stripped
    field, or a None secret all resolve to None (trust nothing).
    """
    if not is_relay_served(config):
        return None
    secret = config.identity_secret
    if secret is None:
        # Relay-served but no secret (local mount / misconfig): trust nothing.
        return None
    user = headers.get(HEADER_USER)
    role = headers.get(HEADER_ROLE)
    signature = headers.get(IDENTITY_SIG_HEADER)
    if user is None or role is None or signature is None:
        return None
    bypass = headers.get(HEADER_AUTH_BYPASS) == "1"
    if not verify_identity(secret, user, role, bypass, signature):
        return None
    return (user, role, bypass)


def trusted_role(config: ServerConfig, headers: Mapping[str, str]) -> Role | None:
    """Return the relay-asserted role, or None if absent/untrusted/invalid."""
    verified = _verified_identity(config, headers)
    if verified is None:
        return None
    try:
        return Role(verified[1])
    except ValueError:
        return None


def trusted_user(config: ServerConfig, headers: Mapping[str, str]) -> str | None:
    """Return the relay-asserted username, or None if absent/untrusted."""
    verified = _verified_identity(config, headers)
    if verified is None:
        return None
    return verified[0]


def is_auth_bypassed(config: ServerConfig, headers: Mapping[str, str]) -> bool:
    """True if the relay vouched for an allowlisted user (skip password)."""
    verified = _verified_identity(config, headers)
    if verified is None:
        return False
    return verified[2]
