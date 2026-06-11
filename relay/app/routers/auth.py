"""Relay account auth endpoints — signup, login, logout, me, agent-token.

Thin glue: input validation and persistence live in the ``accounts``
library; these handlers only translate between HTTP and the library.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from relay.app.rate_limit import (
    auth_agent_token_rate,
    auth_login_rate,
    auth_signup_rate,
    limiter,
)

from accounts import (
    UsernameTakenError,
    UserNotFoundError,
    WeakPasswordError,
    hash_password,
    verify_password,
)
from relay.app.dependencies import (
    get_current_identity,
    get_relay_state,
    is_admin_username,
)
from relay.app.services.session import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SessionIdentity,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/signup")
@limiter.limit(auth_signup_rate)
async def signup(
    request: Request, response: Response, body: SignupRequest
) -> dict[str, object]:
    """Self-register a new account. 409 if the username is taken."""
    store = get_relay_state(request).require_account_store()
    try:
        password_hash = hash_password(body.password)
    except WeakPasswordError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        user = await store.create_user(body.username, password_hash, body.email)
    except UsernameTakenError as exc:
        raise HTTPException(status_code=409, detail="Username already taken") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": user.id, "username": user.username}


def _set_session_cookie(payload: dict[str, object], token: str) -> JSONResponse:
    response = JSONResponse(content=payload)
    # Secure flag is stamped by SecureCookieMiddleware when behind HTTPS.
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path=SESSION_COOKIE_PATH,
    )
    return response


@router.post("/login")
@limiter.limit(auth_login_rate)
async def login(
    request: Request, response: Response, body: LoginRequest
) -> JSONResponse:
    """Authenticate and set the session cookie. 401 on bad credentials."""
    state = get_relay_state(request)
    store = state.require_account_store()
    try:
        user = await store.get_user_by_username(body.username)
    except UserNotFoundError:
        # Generic message — do not reveal whether the username exists.
        raise HTTPException(status_code=401, detail="Invalid username or password")

    try:
        ok = verify_password(body.password, user.password_hash)
    except WeakPasswordError:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not ok or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = state.require_session().issue(user.id, user.username)
    return _set_session_cookie(
        {
            "username": user.username,
            "is_admin": is_admin_username(user.username, state.config),
        },
        token,
    )


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the session cookie."""
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(key=SESSION_COOKIE_NAME, path=SESSION_COOKIE_PATH)
    return response


@router.get("/me")
async def me(
    request: Request,
    identity: SessionIdentity = Depends(get_current_identity),
) -> dict[str, object]:
    """Return the current identity and admin flag. 401 if anonymous."""
    return {
        "user_id": identity.user_id,
        "username": identity.username,
        "is_admin": is_admin_username(
            identity.username, get_relay_state(request).config
        ),
    }


@router.post("/agent-token")
@limiter.limit(auth_agent_token_rate)
async def agent_token(
    request: Request, response: Response, body: LoginRequest
) -> dict[str, object]:
    """Exchange owner credentials for a short-lived agent-owner token.

    Used by the agent during the mount registration handshake (Phase 4) to
    prove it acts on behalf of an account. 401 on bad credentials.
    """
    state = get_relay_state(request)
    store = state.require_account_store()
    try:
        user = await store.get_user_by_username(body.username)
    except UserNotFoundError:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    try:
        ok = verify_password(body.password, user.password_hash)
    except WeakPasswordError:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not ok or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = state.require_session().issue_agent_owner_token(user.id)
    return {"token": token, "user_id": user.id, "username": user.username}
