"""FastAPI dependencies — typed accessors for app-scoped services.

All per-app state lives on ``app.state`` (set by ``create_app``); routes
declare what they need via these functions with ``Depends``. This replaces
the old module-level singletons, so two app instances (e.g. a LAN server
and the relay drop box, or parallel tests) never share state.

WebSocket endpoints use the ``ws_*`` variants (same state, WebSocket scope).
"""

from fastapi import Request, WebSocket

from server.app.config import ServerConfig
from server.app.services.auth_service import AuthTokenService
from server.app.services.clipboard_service import ClipboardService
from server.app.services.connection_manager import ConnectionManager
from server.app.services.file_request_service import FileRequestService
from server.app.services.share_service import ShareLinkService


def get_config(request: Request) -> ServerConfig:
    """The app's validated server configuration."""
    return request.app.state.config


def get_share_service(request: Request) -> ShareLinkService:
    """The app's share-link service."""
    return request.app.state.share_service


def get_clipboard_service(request: Request) -> ClipboardService:
    """The app's clipboard snippet service."""
    return request.app.state.clipboard_service


def get_file_request_service(request: Request) -> FileRequestService:
    """The app's file-request service."""
    return request.app.state.file_request_service


def get_connection_manager(request: Request) -> ConnectionManager:
    """The app's WebSocket device/connection registry."""
    return request.app.state.manager


def get_token_service(request: Request) -> AuthTokenService:
    """The app's session-token service.

    Raises:
        RuntimeError: When the app was built without password protection —
            callers must only depend on this behind a password_hash check.
    """
    token_service = request.app.state.token_service
    if token_service is None:
        raise RuntimeError("App was built without password auth — no token service")
    return token_service


def ws_config(websocket: WebSocket) -> ServerConfig:
    """WebSocket-scope variant of get_config."""
    return websocket.app.state.config


def ws_connection_manager(websocket: WebSocket) -> ConnectionManager:
    """WebSocket-scope variant of get_connection_manager."""
    return websocket.app.state.manager
