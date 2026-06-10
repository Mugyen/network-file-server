"""Pure ASGI middleware for cookie-based authentication gating.

Checks the 'session' cookie against AuthTokenService for all HTTP requests
except exempt paths (login, server-info, static assets).
"""

import json
from http.cookies import SimpleCookie
from typing import Any, Callable

from server.app.config import ServerConfig
from server.app.services.auth_service import AuthTokenService
from server.app.services.relay_identity import is_auth_bypassed

# Type aliases for ASGI
Scope = dict[str, Any]
Receive = Callable[..., Any]
Send = Callable[..., Any]
ASGIApp = Callable[..., Any]

GUARDED_PREFIX = "/api/"
EXEMPT_API_PREFIXES = ("/api/auth/login", "/api/auth/logout", "/api/server-info")


class AuthMiddleware:
    """ASGI middleware that gates HTTP requests behind cookie-based auth.

    WebSocket connections are NOT checked here -- WebSocket auth is handled
    in the endpoint itself (after upgrade) since ASGI middleware cannot
    reliably reject WebSocket connections before upgrade.
    """

    def __init__(self, app: ASGIApp, token_service: AuthTokenService, config: ServerConfig) -> None:
        self._app = app
        self._token_service = token_service
        # Full config so the bypass decision goes through the signature-
        # verifying is_auth_bypassed (relay-served + valid HMAC required).
        self._config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http",):
            # Pass through WebSocket, lifespan, etc.
            await self._app(scope, receive, send)
            return

        path: str = scope.get("path", "")

        # Only gate /api/* paths; let SPA, static files, and /share through
        if not path.startswith(GUARDED_PREFIX):
            await self._app(scope, receive, send)
            return

        # Check exempt API prefixes (login, server-info)
        for prefix in EXEMPT_API_PREFIXES:
            if path.startswith(prefix):
                await self._app(scope, receive, send)
                return

        # Parse cookies from headers
        headers = dict(scope.get("headers", []))

        # Relay-vouched allowlisted user: the relay strips inbound X-WFS-*
        # and injects a SIGNED identity only for authorised accounts.
        # is_auth_bypassed verifies the HMAC against the per-mount secret —
        # a bare/forged bypass header from a LAN client does not pass.
        str_headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        if is_auth_bypassed(self._config, str_headers):
            await self._app(scope, receive, send)
            return

        cookie_header = headers.get(b"cookie", b"").decode("latin-1")

        token = _extract_session_cookie(cookie_header)
        if token is not None and self._token_service.validate_token(token):
            await self._app(scope, receive, send)
            return

        # Unauthorized -- return 401 JSON
        await _send_401(send)


def _extract_session_cookie(cookie_header: str) -> str | None:
    """Extract the 'session' cookie value from a raw Cookie header string."""
    if not cookie_header:
        return None
    cookie: SimpleCookie[str] = SimpleCookie()
    cookie.load(cookie_header)
    morsel = cookie.get("session")
    if morsel is None:
        return None
    return morsel.value


async def _send_401(send: Send) -> None:
    """Send a 401 Unauthorized JSON response via raw ASGI."""
    body = json.dumps({"detail": "Not authenticated"}).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode("latin-1")],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
