"""Authentication API router.

Provides POST /api/auth/login for password verification and session cookie management,
and POST /api/auth/logout for clearing the session cookie.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from server.app.config import get_server_config
from server.app.models.schemas import LoginRequest
from server.app.services.auth_service import get_token_service, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(request: LoginRequest) -> JSONResponse:
    """Verify password and set session cookie on success.

    Returns 200 with {"status": "ok"} and sets httpOnly session cookie.
    Returns 401 with {"detail": "Invalid password"} on failure.
    """
    config = get_server_config()

    if config.password_hash is None:
        raise HTTPException(status_code=400, detail="Password not configured")

    if len(request.password) == 0:
        raise HTTPException(status_code=401, detail="Invalid password")

    if not verify_password(request.password, config.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    token_service = get_token_service()
    token = token_service.create_token()

    cookie_path = f"/m/{config.mount_code}/" if config.mount_code is not None else "/"

    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        path=cookie_path,
    )
    return response


@router.post("/logout")
def logout() -> JSONResponse:
    """Clear the session cookie.

    Returns 200 with {"status": "ok"} and expires the session cookie.
    Cookie path is scoped to /m/{mount_code}/ for remote mounts, or / for LAN mode.
    """
    config = get_server_config()
    cookie_path = f"/m/{config.mount_code}/" if config.mount_code is not None else "/"

    response = JSONResponse(content={"status": "ok"})
    response.set_cookie(
        key="session",
        value="",
        httponly=True,
        samesite="lax",
        path=cookie_path,
        max_age=0,
    )
    return response
