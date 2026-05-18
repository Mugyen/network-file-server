"""FastAPI dependencies for relay account auth.

Anonymous access is a legitimate state for the relay (open mounts, the
landing page), so the optional accessor returns ``None`` for "no/!invalid
session" rather than raising. Endpoint guards that require a login raise
``HTTPException`` (JSON 401/403) — the redirect-to-login behaviour belongs
to the mount proxy (Phase 5), not the JSON API.
"""

from fastapi import Depends, HTTPException, Request

from relay.app.config import get_config
from relay.app.exceptions import InvalidSessionError
from relay.app.services.session import (
    SESSION_COOKIE_NAME,
    SessionIdentity,
    get_relay_session,
)


def get_optional_identity(request: Request) -> SessionIdentity | None:
    """Return the session identity if a valid cookie is present, else None.

    Never raises for missing/invalid sessions — anonymity is valid here.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return get_relay_session().verify_session_cookie(token)
    except InvalidSessionError:
        # Treat a tampered/expired cookie as anonymous (do not 500).
        return None


async def get_current_identity(request: Request) -> SessionIdentity:
    """Require a logged-in user. Raises 401 if anonymous/invalid."""
    identity = get_optional_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return identity


def is_admin_username(username: str) -> bool:
    """True if the username is configured as a relay admin (case-insensitive)."""
    return username.strip().lower() in set(get_config().admin_users)


async def require_admin(
    identity: SessionIdentity = Depends(get_current_identity),
) -> SessionIdentity:
    """Require an authenticated admin. Raises 403 for non-admins."""
    if not is_admin_username(identity.username):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return identity
