"""FastAPI application factory.

Creates the app with CORS middleware and router mounting.
Conditionally mounts SPA static files if client/dist exists.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.app.config import get_server_config
from server.app.exceptions import AccessDeniedError, ReadOnlyError
from server.app.middleware.auth_middleware import AuthMiddleware
from server.app.routers.auth import router as auth_router
from server.app.routers.clipboard import router as clipboard_router
from server.app.routers.file_requests import router as file_requests_router
from server.app.routers.files import router as files_router
from server.app.routers.server_info import router as server_info_router
from server.app.routers.share import router as share_router
from server.app.routers.share_target import router as share_target_router
from server.app.routers.websocket import router as websocket_router
from server.app.services.auth_service import get_token_service
from server.app.services.share_service import ShareLinkService, set_share_service


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    - Adds CORSMiddleware with wildcard origins for LAN access.
    - Includes the files API router and server-info router.
    - Mounts SPA static files if client/dist exists (production mode).
    """
    application = FastAPI(title="Network File Server")

    # CORS: allow all origins for LAN access
    # Note: allow_credentials is NOT set to True (mutually exclusive with wildcard origins per CORS spec)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router)
    application.include_router(clipboard_router)
    application.include_router(file_requests_router)
    application.include_router(files_router)
    application.include_router(server_info_router)
    application.include_router(share_router)
    application.include_router(share_target_router)
    application.include_router(websocket_router)

    # Exception handlers for access control errors
    @application.exception_handler(ReadOnlyError)
    async def read_only_handler(request: Request, exc: ReadOnlyError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": "Server is in read-only mode"},
        )

    @application.exception_handler(AccessDeniedError)
    async def access_denied_handler(request: Request, exc: AccessDeniedError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied"},
        )

    # Conditionally add auth middleware when password is set.
    # Must be added AFTER CORSMiddleware (Starlette processes in reverse order,
    # so AuthMiddleware added second runs first in the request pipeline).
    try:
        config = get_server_config()
        if config.password_hash is not None:
            application.add_middleware(AuthMiddleware, token_service=get_token_service())
    except RuntimeError:
        pass  # Config not set yet (e.g., during import-time app creation)

    # Initialize ShareLinkService if not already set (e.g., during test setup)
    try:
        from server.app.services.share_service import get_share_service
        get_share_service()  # Check if already initialized
    except RuntimeError:
        import secrets as _secrets
        _share_secret = _secrets.token_hex(32)
        set_share_service(ShareLinkService(_share_secret))

    # SPA catch-all: mount static files if client/dist exists
    # Resolve relative to the project root (two levels up from this file),
    # not the CWD, so the server works regardless of where it's launched from.
    project_root = Path(__file__).resolve().parent.parent.parent
    client_dist = project_root / "client" / "dist"
    if client_dist.exists() and client_dist.is_dir():
        assets_dir = client_dist / "assets"
        if assets_dir.exists():
            application.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        index_html = client_dist / "index.html"

        @application.get("/{path:path}")
        def spa_catch_all(path: str) -> FileResponse:
            """Serve SPA index.html for all non-API routes."""
            # Check if the requested path maps to a static file
            static_file = client_dist / path
            if static_file.exists() and static_file.is_file():
                return FileResponse(str(static_file))
            return FileResponse(str(index_html))

    return application


app = create_app()
