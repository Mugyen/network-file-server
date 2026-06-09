"""Tests for SecureCookieMiddleware.

Verifies that the middleware stamps the Secure flag on Set-Cookie headers
when the request arrives via HTTPS (X-Forwarded-Proto: https), and does
nothing when the request is plain HTTP.
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import Response
from httpx import ASGITransport, AsyncClient

from relay.app.middleware.secure_cookies import SecureCookieMiddleware


def _make_cookie_app() -> FastAPI:
    """Create a minimal FastAPI app that sets a cookie on GET /set-cookie."""
    app = FastAPI()

    @app.get("/set-cookie")
    def set_cookie() -> Response:
        resp = Response(content="ok")
        resp.set_cookie(key="session", value="abc123")
        return resp

    @app.get("/set-cookie-already-secure")
    def set_cookie_already_secure() -> Response:
        resp = Response(content="ok")
        resp.set_cookie(key="session", value="abc123", secure=True)
        return resp

    @app.get("/set-multiple-cookies")
    def set_multiple_cookies() -> Response:
        resp = Response(content="ok")
        resp.set_cookie(key="session", value="abc123")
        resp.set_cookie(key="csrf", value="xyz789")
        return resp

    @app.get("/no-cookie")
    def no_cookie() -> Response:
        return Response(content="ok")

    app.add_middleware(SecureCookieMiddleware)
    return app


@pytest.fixture
def cookie_app() -> FastAPI:
    return _make_cookie_app()


@pytest.fixture
async def cookie_client(cookie_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=cookie_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.anyio
async def test_secure_flag_added_when_https(cookie_client: AsyncClient) -> None:
    """When X-Forwarded-Proto is https, Set-Cookie must include Secure."""
    response = await cookie_client.get(
        "/set-cookie",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    assert "; Secure" in cookie_header or ";Secure" in cookie_header


@pytest.mark.anyio
async def test_no_secure_flag_when_http(cookie_client: AsyncClient) -> None:
    """When X-Forwarded-Proto is http, Set-Cookie is unchanged (no Secure)."""
    response = await cookie_client.get(
        "/set-cookie",
        headers={"X-Forwarded-Proto": "http"},
    )
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    # The cookie should NOT have Secure flag
    assert "; Secure" not in cookie_header
    assert ";Secure" not in cookie_header


@pytest.mark.anyio
async def test_no_secure_flag_when_no_proto_header(
    cookie_client: AsyncClient,
) -> None:
    """When X-Forwarded-Proto is absent, Set-Cookie is unchanged."""
    response = await cookie_client.get("/set-cookie")
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    assert "; Secure" not in cookie_header
    assert ";Secure" not in cookie_header


@pytest.mark.anyio
async def test_no_duplicate_secure_flag(cookie_client: AsyncClient) -> None:
    """When Set-Cookie already has Secure, the middleware must NOT double-stamp."""
    response = await cookie_client.get(
        "/set-cookie-already-secure",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    # Count occurrences of "secure" (case-insensitive)
    secure_count = cookie_header.lower().count("secure")
    assert secure_count == 1, f"Expected exactly 1 'Secure', found {secure_count} in: {cookie_header}"


@pytest.mark.anyio
async def test_multiple_set_cookie_headers(cookie_client: AsyncClient) -> None:
    """When response has multiple Set-Cookie headers, all get the Secure flag."""
    response = await cookie_client.get(
        "/set-multiple-cookies",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    # httpx collapses multi-value headers; use headers.multi_items()
    set_cookies = [
        v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"
    ]
    assert len(set_cookies) >= 2, f"Expected >= 2 Set-Cookie headers, got {len(set_cookies)}"
    for cookie_val in set_cookies:
        assert (
            "; Secure" in cookie_val or ";Secure" in cookie_val
        ), f"Missing Secure flag in: {cookie_val}"


@pytest.mark.anyio
async def test_non_http_scopes_passthrough() -> None:
    """WebSocket scope passes through without modification.

    We verify the middleware doesn't crash on non-HTTP scopes by creating
    a raw ASGI app that handles 'websocket' scope.
    """
    received_scope: dict = {}

    async def inner_app(scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        received_scope.update(scope)
        if scope["type"] == "websocket":
            # Just accept and close
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.close", "code": 1000})

    middleware = SecureCookieMiddleware(inner_app)

    # Simulate a websocket scope
    scope = {
        "type": "websocket",
        "asgi": {"version": "3.0"},
        "headers": [],
    }

    messages_sent: list[dict] = []

    async def receive() -> dict:  # type: ignore[no-untyped-def]
        return {"type": "websocket.connect"}

    async def send(message: dict) -> None:
        messages_sent.append(message)

    await middleware(scope, receive, send)

    assert received_scope["type"] == "websocket"
    assert any(m["type"] == "websocket.accept" for m in messages_sent)


@pytest.mark.anyio
async def test_no_cookie_response_unaffected(cookie_client: AsyncClient) -> None:
    """Responses without Set-Cookie headers pass through unchanged."""
    response = await cookie_client.get(
        "/no-cookie",
        headers={"X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    assert response.text == "ok"
    set_cookies = [
        v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"
    ]
    assert len(set_cookies) == 0
