"""ASGI middleware that stamps the Secure flag on Set-Cookie headers behind HTTPS.

When a request arrives with X-Forwarded-Proto: https (e.g., behind Cloud Run
TLS termination), this middleware appends "; Secure" to every Set-Cookie
response header that does not already contain it. Non-HTTP scopes (WebSocket)
and plain HTTP requests pass through unchanged.

Uses raw ASGI (not BaseHTTPMiddleware) for correctness with streaming responses.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecureCookieMiddleware:
    """Stamps Secure flag on Set-Cookie headers when behind HTTPS proxy."""

    def __init__(self, app: ASGIApp) -> None:
        self._app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # Check X-Forwarded-Proto from request headers
        is_https: bool = _is_forwarded_https(scope)

        if not is_https:
            await self._app(scope, receive, send)
            return

        # Wrap send to intercept response headers
        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                stamped_headers: list[tuple[bytes, bytes]] = []
                for key, value in headers:
                    if key.lower() == b"set-cookie" and b"secure" not in value.lower():
                        stamped_headers.append((key, value + b"; Secure"))
                    else:
                        stamped_headers.append((key, value))
                message = {**message, "headers": stamped_headers}
            await send(message)

        await self._app(scope, receive, send_wrapper)


def _is_forwarded_https(scope: Scope) -> bool:
    """Check if X-Forwarded-Proto header indicates HTTPS.

    Args:
        scope: The ASGI scope containing request headers.

    Returns:
        True if X-Forwarded-Proto is 'https', False otherwise.
    """
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for key, value in headers:
        if key.lower() == b"x-forwarded-proto" and value.lower() == b"https":
            return True
    return False
