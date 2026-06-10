"""FastAPI dependencies for relay account auth.

Anonymous access is a legitimate state for the relay (open mounts, the
landing page), so the optional accessor returns ``None`` for "no/!invalid
session" rather than raising. Endpoint guards that require a login raise
``HTTPException`` (JSON 401/403) — the redirect-to-login behaviour belongs
to the mount proxy (Phase 5), not the JSON API.

All per-app services are reached through ``RelayState`` on
``request.app.state.relay`` — there are no module-level singletons.
"""

from fastapi import Depends, HTTPException, Request

from accounts import AccountStore
from relay.app.config import RelayConfig
from relay.app.exceptions import InvalidSessionError
from relay.app.services.session import SESSION_COOKIE_NAME, SessionIdentity
from relay.app.state import RelayState


def get_relay_state(request: Request) -> RelayState:
    """Return the per-app RelayState attached by create_relay_app.

    Raises:
        RuntimeError: If the app was built without create_relay_app.
    """
    state = getattr(request.app.state, "relay", None)
    if not isinstance(state, RelayState):
        raise RuntimeError("app.state.relay is not a RelayState (wrong app factory?)")
    return state


def get_account_store_dep(request: Request) -> AccountStore:
    """Depends-style accessor for the per-app account store."""
    return get_relay_state(request).require_account_store()


def get_optional_identity(request: Request) -> SessionIdentity | None:
    """Return the session identity if a valid cookie is present, else None.

    Never raises for missing/invalid sessions — anonymity is valid here.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        session = get_relay_state(request).require_session()
        return session.verify_session_cookie(token)
    except InvalidSessionError:
        # Treat a tampered/expired cookie as anonymous (do not 500).
        return None


async def get_current_identity(request: Request) -> SessionIdentity:
    """Require a logged-in user. Raises 401 if anonymous/invalid."""
    identity = get_optional_identity(request)
    if identity is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return identity


def is_admin_username(username: str, config: RelayConfig) -> bool:
    """True if the username is configured as a relay admin (case-insensitive)."""
    return username.strip().lower() in set(config.admin_users)


async def require_admin(
    request: Request,
    identity: SessionIdentity = Depends(get_current_identity),
) -> SessionIdentity:
    """Require an authenticated admin. Raises 403 for non-admins."""
    if not is_admin_username(identity.username, get_relay_state(request).config):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return identity
