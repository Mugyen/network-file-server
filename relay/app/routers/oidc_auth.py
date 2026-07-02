"""Optional SSO login via OIDC (the identity broker, Authentik).

A *third* way to establish the relay's session cookie, alongside password
login and anonymous access. The flow:

    GET /auth/oidc/login    -> sign a `state` (post-login `next` + CSRF nonce),
                               set the nonce as a short cookie, 302 to the IdP.
    GET /auth/oidc/callback -> verify state + CSRF cookie, exchange the code,
                               read canonical claims from userinfo, resolve or
                               create a local account keyed on the OIDC `sub`
                               (a UUID, NEVER email), then issue the SAME
                               `wfs_session` cookie the password flow issues.

Because it mints the identical session, every existing authorization path
(private mounts, per-user storage, admin) works unchanged. Anonymous access and
password accounts are untouched. This router is only mounted when SSO is
configured (see relay/app/config.py:oidc_enabled).
"""

import logging
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from accounts import (
    DuplicateMembershipError,
    GroupNameTakenError,
    GroupNotFoundError,
    SubjectType,
    UsernameTakenError,
    UserNotFoundError,
)
from relay.app.dependencies import get_relay_state
from relay.app.exceptions import InvalidSessionError
from relay.app.services.oidc import OidcError
from relay.app.services.session import SESSION_COOKIE_NAME, SESSION_COOKIE_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oidc", tags=["auth"])

PROVIDER = "authentik"
_CSRF_COOKIE = "wfs_oidc_csrf"
_CSRF_COOKIE_PATH = "/auth/oidc"
_CSRF_MAX_AGE = 600
_LOGIN_ERROR_REDIRECT = "/login?sso_error=1"


def _safe_next(raw: str | None) -> str:
    """Only allow same-site absolute paths (blocks open redirects)."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/"


def _derive_username(claims: dict) -> str:
    """Pick a readable, stable-ish base username from the claims.

    Display/admin-matching only — the account's identity is the OIDC `sub`.
    """
    for key in ("preferred_username", "nickname", "name"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            base = value.strip()
            break
    else:
        email = claims.get("email")
        base = email.split("@")[0] if isinstance(email, str) and "@" in email else "user"
    cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "-_.").strip("-_.")
    return cleaned or "user"


@router.get("/login")
async def oidc_login(request: Request) -> RedirectResponse:
    """Begin the OIDC code flow: 302 to the identity broker."""
    state = get_relay_state(request)
    oidc = state.require_oidc()
    next_url = _safe_next(request.query_params.get("next"))
    csrf = secrets.token_urlsafe(24)
    signed_state = state.require_session().issue_oauth_state(next_url, csrf)
    try:
        url = await oidc.authorize_url(signed_state)
    except OidcError:
        logger.exception("OIDC authorize URL build failed")
        return RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302)
    response = RedirectResponse(url, status_code=302)
    # Bind the round-trip to this browser; Secure is stamped by middleware.
    response.set_cookie(
        key=_CSRF_COOKIE, value=csrf, max_age=_CSRF_MAX_AGE,
        httponly=True, samesite="lax", path=_CSRF_COOKIE_PATH,
    )
    return response


@router.get("/callback")
async def oidc_callback(request: Request) -> RedirectResponse:
    """Complete the OIDC flow and establish the relay session."""
    state = get_relay_state(request)

    if request.query_params.get("error"):
        logger.info("OIDC callback returned error: %s", request.query_params.get("error"))
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))

    code = request.query_params.get("code")
    raw_state = request.query_params.get("state")
    if not code or not raw_state:
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))

    # 1. Verify the signed state and match it against the CSRF cookie.
    try:
        next_url, csrf = state.require_session().verify_oauth_state(raw_state)
    except InvalidSessionError:
        logger.info("OIDC callback: invalid/expired state")
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))
    cookie_csrf = request.cookies.get(_CSRF_COOKIE)
    if not cookie_csrf or not secrets.compare_digest(cookie_csrf, csrf):
        logger.warning("OIDC callback: CSRF mismatch")
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))

    # 2. Exchange the code and read canonical claims from userinfo.
    oidc = state.require_oidc()
    try:
        tokens = await oidc.exchange_code(code)
        claims = await oidc.fetch_userinfo(tokens["access_token"])
    except (OidcError, KeyError):
        logger.exception("OIDC token/userinfo exchange failed")
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))

    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        logger.warning("OIDC callback: userinfo missing sub")
        return _clear_csrf(RedirectResponse(_LOGIN_ERROR_REDIRECT, status_code=302))

    # 3. Resolve or create the local account keyed on (provider, sub).
    store = state.require_account_store()
    user = await _resolve_or_create(store, sub, claims)

    # 4. Optionally sync IdP groups (app:files:*) to local relay groups.
    prefix = state.config.oidc_group_prefix
    if prefix:
        await _sync_groups(store, user.id, claims, prefix)

    # 5. Mint the SAME session the password flow mints; land on `next`.
    token = state.require_session().issue(user.id, user.username)
    response = RedirectResponse(next_url, status_code=302)
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=token,
        httponly=True, samesite="lax", path=SESSION_COOKIE_PATH,
    )
    return _clear_csrf(response)


def _clear_csrf(response: RedirectResponse) -> RedirectResponse:
    response.delete_cookie(key=_CSRF_COOKIE, path=_CSRF_COOKIE_PATH)
    return response


async def _resolve_or_create(store, sub: str, claims: dict):
    """Find the account linked to this OIDC subject, or create a fresh one.

    We NEVER auto-merge with a password account by matching username/email —
    that would be an account-takeover path. A new SSO subject gets a new local
    account.
    """
    try:
        return await store.get_user_by_external_id(PROVIDER, sub)
    except UserNotFoundError:
        pass
    base = _derive_username(claims)
    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    for i in range(50):
        candidate = base if i == 0 else f"{base}-{i + 1}"
        try:
            return await store.create_external_user(PROVIDER, sub, candidate, email)
        except UsernameTakenError:
            # Either a username clash (try next) or a concurrent first-login
            # that just linked this same sub (adopt it).
            try:
                return await store.get_user_by_external_id(PROVIDER, sub)
            except UserNotFoundError:
                continue
    raise OidcError("could not allocate a unique username for the SSO account")


async def _sync_groups(store, user_id: int, claims: dict, prefix: str) -> None:
    """Additively mirror IdP groups matching ``prefix`` into local groups.

    Additive only: memberships are added, never revoked, so manual grants and
    access-request approvals are never fought. Group names are the contract's
    ``app:<service>:<role>`` strings, referenced by mount allowlists.
    """
    groups = claims.get("groups")
    if not isinstance(groups, list):
        return
    for name in groups:
        if not isinstance(name, str) or not name.startswith(prefix):
            continue
        try:
            group = await store.get_group_by_name(name)
        except GroupNotFoundError:
            try:
                group = await store.create_group(name)
            except GroupNameTakenError:
                group = await store.get_group_by_name(name)
        try:
            await store.add_member(group.id, SubjectType.USER, user_id)
        except DuplicateMembershipError:
            pass
