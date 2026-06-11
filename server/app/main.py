"""FastAPI application factory.

``create_app(config)`` builds a fully self-contained app instance: all
services (auth tokens, share links, clipboard, file requests, connection
manager) are constructed here and attached to ``app.state``. There are no
module-level singletons and no module-level app — multiple instances can
coexist in one process (LAN server, relay drop box, parallel tests).

Routes access services via ``server.app.dependencies`` with ``Depends``.
"""

import logging
import secrets

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.app.config import ServerConfig
from server.app.error_handlers import register_exception_handlers
from server.app.middleware.auth_middleware import AuthMiddleware
from server.app.routers.auth import router as auth_router
from server.app.routers.clipboard import router as clipboard_router
from server.app.routers.file_requests import router as file_requests_router
from server.app.routers.files import router as files_router
from server.app.routers.server_info import router as server_info_router
from server.app.routers.share import router as share_router
from server.app.routers.share_target import router as share_target_router
from server.app.routers.websocket import router as websocket_router
from server.app.services.auth_service import AuthTokenService
from server.app.services.clipboard_service import ClipboardService
from server.app.services.connection_manager import ConnectionManager
from server.app.services.file_request_service import FileRequestService
from server.app.services.share_service import ShareLinkService
from server.app.services.sqlite_store import open_state_store
from shared.paths import repo_root
from shared.spa import spa_shell_response

logger = logging.getLogger("server.app")


def create_app(config: ServerConfig) -> FastAPI:
    """Create and configure a FastAPI application for the given config.

    - Attaches config and all services to ``app.state``.
    - Adds CORSMiddleware with wildcard origins for LAN access.
    - Adds AuthMiddleware when a password hash is configured.
    - Serves the SPA via a catch-all route: the built client/dist bundle when
      present, else a placeholder shell (``shared.spa``).
    """
    if not isinstance(config, ServerConfig):
        raise ValueError(f"config must be a ServerConfig, got {type(config)!r}")

    application = FastAPI(title="Network File Server")

    # --- App-scoped state (replaces module-level singletons) -------------
    application.state.config = config

    data_dir = config.shared_folder.parent / ".wfs_data"
    # One store per app instance — no process-level cache (see open_state_store).
    store = open_state_store(data_dir)
    application.state.store = store
    share_secret = store.get_or_create_share_secret()
    application.state.share_service = ShareLinkService(share_secret, store)
    application.state.clipboard_service = ClipboardService(store)
    application.state.file_request_service = FileRequestService(store)
    application.state.manager = ConnectionManager()

    # Injected by an in-process host (relay drop box) after creation; None
    # means TTL tracking is absent (standalone LAN mode).
    application.state.file_ttl_provider = None

    # Session tokens exist only for password-protected apps.
    if config.password_hash is not None:
        application.state.token_service = AuthTokenService(secrets.token_hex(32))
    else:
        application.state.token_service = None

    # --- Middleware -------------------------------------------------------
    # CORS: allow all origins for LAN access
    # Note: allow_credentials is NOT set to True (mutually exclusive with wildcard origins per CORS spec)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Conditionally add auth middleware when password is set.
    # Must be added AFTER CORSMiddleware (Starlette processes in reverse order,
    # so AuthMiddleware added second runs first in the request pipeline).
    if config.password_hash is not None:
        application.add_middleware(
            AuthMiddleware,
            token_service=application.state.token_service,
            config=config,
        )

    # --- Routers ------------------------------------------------------------
    application.include_router(auth_router)
    application.include_router(clipboard_router)
    application.include_router(file_requests_router)
    application.include_router(files_router)
    application.include_router(server_info_router)
    application.include_router(share_router)
    application.include_router(share_target_router)
    application.include_router(websocket_router)

    # Central domain-exception -> HTTP mapping (see server/app/error_handlers.py)
    register_exception_handlers(application)

    # SPA catch-all: serve the built client bundle when present; fall back to
    # the shared placeholder shell when client/dist is absent (dev/CI without
    # a client build) so SPA routes resolve with 200 rather than 404.
    client_dist = repo_root() / "client" / "dist"
    assets_dir = client_dist / "assets"
    if assets_dir.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="assets",
        )

    index_html = client_dist / "index.html"

    @application.get("/{path:path}")
    def spa_catch_all(path: str) -> Response:
        """Serve SPA index.html (or the placeholder shell) for non-API routes."""
        # Check if the requested path maps to a static file in the bundle
        static_file = client_dist / path
        if static_file.is_file():
            return FileResponse(str(static_file))
        return spa_shell_response(index_html)

    return application
