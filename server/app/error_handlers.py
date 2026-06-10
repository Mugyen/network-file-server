"""Central domain-exception -> HTTP response mapping for the server app.

Routers and services raise domain exceptions (server/app/exceptions.py) and
never construct error responses themselves; the handlers registered here are
the single source of truth for status codes and response shapes.

All error responses use FastAPI's conventional ``{"detail": ...}`` shape.
``FileConflictError`` and ``InvalidFileNameError`` carry extra fields the
client conflict dialog can use.

``FileNotFoundError`` (builtin) is mapped app-wide to 404: in a file server
"the file is not there" is the domain meaning of that exception. Services
must not leak it for internal bookkeeping files.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from server.app.exceptions import (
    AccessDeniedError,
    FileConflictError,
    InvalidFileNameError,
    InvalidFileRequestError,
    PathTraversalError,
    ReadOnlyError,
    SnippetNotFoundError,
    SnippetValidationError,
)
from server.app.services.share_service import ShareLinkNotFoundError


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain-exception handlers on the given app.

    Raises:
        ValueError: If ``app`` is not a FastAPI instance.
    """
    if not isinstance(app, FastAPI):
        raise ValueError(f"app must be a FastAPI instance, got {type(app)!r}")

    @app.exception_handler(PathTraversalError)
    async def path_traversal(request: Request, exc: PathTraversalError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def not_found(request: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found"})

    @app.exception_handler(FileConflictError)
    async def conflict(request: Request, exc: FileConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "path": exc.path,
                "existing_path": exc.existing_path,
            },
        )

    @app.exception_handler(InvalidFileNameError)
    async def invalid_name(request: Request, exc: InvalidFileNameError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "name": exc.name, "reason": exc.reason},
        )

    @app.exception_handler(InvalidFileRequestError)
    async def invalid_request(
        request: Request, exc: InvalidFileRequestError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ReadOnlyError)
    async def read_only(request: Request, exc: ReadOnlyError) -> JSONResponse:
        return JSONResponse(
            status_code=403, content={"detail": "Server is in read-only mode"}
        )

    @app.exception_handler(AccessDeniedError)
    async def access_denied(request: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Access denied"})

    @app.exception_handler(ShareLinkNotFoundError)
    async def share_not_found(
        request: Request, exc: ShareLinkNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Share link not found"})

    @app.exception_handler(SnippetNotFoundError)
    async def snippet_not_found(
        request: Request, exc: SnippetNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(SnippetValidationError)
    async def snippet_invalid(
        request: Request, exc: SnippetValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
