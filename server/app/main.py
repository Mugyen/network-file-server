"""FastAPI application factory.

Creates the app with CORS middleware and router mounting.
Conditionally mounts SPA static files if client/dist exists.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.app.routers.files import router as files_router
from server.app.routers.server_info import router as server_info_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    - Adds CORSMiddleware with wildcard origins for LAN access.
    - Includes the files API router and server-info router.
    - Mounts SPA static files if client/dist exists (production mode).
    """
    application = FastAPI(title="WiFi File Server")

    # CORS: allow all origins for LAN access
    # Note: allow_credentials is NOT set to True (mutually exclusive with wildcard origins per CORS spec)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(files_router)
    application.include_router(server_info_router)

    # SPA catch-all: mount static files if client/dist exists
    client_dist = Path("client/dist")
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
