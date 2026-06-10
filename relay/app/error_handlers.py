"""Central domain-exception -> HTTP response mapping for the relay app.

JSON routers raise domain exceptions (relay/app/exceptions.py) and never
construct error responses themselves. The proxy (mount_proxy) deliberately
keeps its own local handling for browser-facing routes — it renders HTML
error pages and login redirects, which are context-dependent; these handlers
are the safety net so an uncaught domain exception can never surface as a 500.

All responses use FastAPI's conventional ``{"detail": ...}`` shape.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from relay.app.exceptions import (
    AccessDeniedError,
    AccessRequestNotFoundError,
    AuthenticationRequiredError,
    InvalidSessionError,
    MountExpiredError,
    MountNotFoundError,
    MountOfflineError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain-exception handlers on the given app.

    Raises:
        ValueError: If ``app`` is not a FastAPI instance.
    """
    if not isinstance(app, FastAPI):
        raise ValueError(f"app must be a FastAPI instance, got {type(app)!r}")

    @app.exception_handler(MountNotFoundError)
    async def mount_not_found(request: Request, exc: MountNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MountOfflineError)
    async def mount_offline(request: Request, exc: MountOfflineError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(MountExpiredError)
    async def mount_expired(request: Request, exc: MountExpiredError) -> JSONResponse:
        return JSONResponse(status_code=410, content={"detail": str(exc)})

    @app.exception_handler(AccessRequestNotFoundError)
    async def access_request_not_found(
        request: Request, exc: AccessRequestNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidSessionError)
    async def invalid_session(request: Request, exc: InvalidSessionError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationRequiredError)
    async def auth_required(
        request: Request, exc: AuthenticationRequiredError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AccessDeniedError)
    async def access_denied(request: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})
