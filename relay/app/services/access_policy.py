"""Mount access authorization — the single decision point for the proxy.

Implements the access-decision model:

1. An allowlisted signed-in user is ALLOWED with their effective role
   (relay vouches; the server password is bypassed downstream).
2. Otherwise:
   - OPEN mount        -> ALLOWED anonymously (server applies its own
     password / read-only / receive exactly as before).
   - RESTRICTED + has  -> ALLOWED passthrough so the server's existing
     password gate can challenge (password is the documented fallback).
   - RESTRICTED + none -> DENIED: AuthenticationRequiredError (anonymous)
     or AccessDeniedError (logged in but not allowlisted).

Header injection (X-WFS-*) is layered on top of this in the proxy
(Phase 6); this module only decides allow/deny + effective identity.
"""

from collections.abc import Mapping
import logging
from dataclasses import dataclass

from accounts import AccessMode, AccountStore, Role, SubjectType, UserNotFoundError
from relay.app.exceptions import (
    AccessDeniedError,
    AuthenticationRequiredError,
    InvalidSessionError,
    MountNotFoundError,
)
from relay.app.services.mount_registry import MountPolicy
from relay.app.services.session import (
    SESSION_COOKIE_NAME,
    RelaySession,
    SessionIdentity,
)

logger = logging.getLogger("relay.access_policy")

# Most-permissive-wins ordering when a user matches several allowlist
# entries (e.g. directly and via a group).
_ROLE_RANK: dict[Role, int] = {Role.READ: 1, Role.RECEIVE: 2, Role.WRITE: 3}


@dataclass(frozen=True)
class AccessDecision:
    """Outcome of an allow decision.

    identified=True means an allowlisted account was matched and ``role``
    is its effective role (used by Phase 6 to inject trusted headers and
    bypass the server password). identified=False is an anonymous /
    password-fallback passthrough (no identity injected).
    """

    identified: bool
    username: str | None
    role: Role | None


def identity_from_cookies(
    cookies: Mapping[str, str],
    session: "RelaySession | None",
) -> SessionIdentity | None:
    """Resolve a relay session identity from request/websocket cookies.

    Returns None for missing/invalid sessions (anonymous is valid). A None
    ``session`` (signer not wired — e.g. minimal test apps) also resolves
    to anonymous rather than failing the request.
    """
    token = cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    if session is None:
        return None
    try:
        return session.verify_session_cookie(token)
    except InvalidSessionError:
        return None


def _highest_role(roles: list[Role]) -> Role:
    return max(roles, key=lambda r: _ROLE_RANK[r])


async def _matched_role(
    policy: MountPolicy, identity: SessionIdentity, store: "AccountStore | None"
) -> Role | None:
    """Return the effective role if the identity is on the allowlist, else None.

    A None ``store`` (accounts not wired) matches nothing — the request
    proceeds as non-allowlisted rather than erroring.
    """
    if store is None:
        return None
    try:
        group_ids = await store.resolve_user_group_ids(identity.user_id)
    except UserNotFoundError:
        # Session references a deleted account — treat as not allowlisted.
        return None

    matched: list[Role] = []
    for entry in policy.entries:
        if (
            entry.subject_type is SubjectType.USER
            and entry.subject_id == identity.user_id
        ):
            matched.append(entry.role)
        elif (
            entry.subject_type is SubjectType.GROUP
            and entry.subject_id in group_ids
        ):
            matched.append(entry.role)
    if not matched:
        return None
    return _highest_role(matched)


async def authorize(
    registry,
    account_store: "AccountStore | None",
    code: str,
    identity: SessionIdentity | None,
) -> AccessDecision:
    """Decide whether a request for ``code`` may proceed.

    Raises:
        AuthenticationRequiredError: anonymous request to a restricted,
            password-less mount (proxy should send to login).
        AccessDeniedError: authenticated-but-not-allowlisted request to a
            restricted, password-less mount (proxy should 403).
    """
    try:
        policy: MountPolicy = await registry.get_policy(code)
    except MountNotFoundError:
        # Mount row absent (vanished between checks): fail open here — the
        # proxy's subsequent get_connection() renders the not_found page.
        logger.debug("authorize: no policy row for code=%s, failing open", code)
        return AccessDecision(identified=False, username=None, role=None)

    if identity is not None:
        role = await _matched_role(policy, identity, account_store)
        if role is not None:
            return AccessDecision(
                identified=True, username=identity.username, role=role
            )

    # LEGACY (pre-v1.3, no policy ever recorded) is treated as OPEN, but as a
    # named, logged state rather than an implicit absence.
    if policy.access_mode is AccessMode.LEGACY:
        logger.info("authorize: legacy mount code=%s treated as open", code)
        return AccessDecision(
            identified=False,
            username=identity.username if identity is not None else None,
            role=None,
        )

    if policy.access_mode is AccessMode.OPEN:
        return AccessDecision(
            identified=False,
            username=identity.username if identity is not None else None,
            role=None,
        )

    # RESTRICTED from here on.
    if policy.has_password:
        # Password is the documented fallback for non-allowlisted users.
        return AccessDecision(identified=False, username=None, role=None)

    if identity is None:
        raise AuthenticationRequiredError(code)
    raise AccessDeniedError(code, identity.username)
