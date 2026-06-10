"""Tests for SlowAPI rate limiting on proxy requests, mount registration rate limiting, and 429 error handling."""

import json
import os
import time
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.main import create_relay_app
from relay.app.rate_limit import get_client_ip
from tests.relay.conftest import MockTunnelConnection, _setup_in_memory_registry


pytestmark = pytest.mark.anyio


async def _make_rate_limited_app(proxy_rate: str):
    """Create a relay app with a tight proxy rate limit for testing.

    Each test gets a fresh app, registry, and limiter to avoid cross-test state leakage.

    Returns:
        Tuple of (app, registry) -- caller should close registry when done.
    """
    with patch.dict(os.environ, {
        "RELAY_PROXY_REQUEST_RATE": proxy_rate,
        "RELAY_DB_PATH": ":memory:",
    }):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    return app, registry


async def _register_mock_connection(registry, code: str) -> MockTunnelConnection:
    """Register a MockTunnelConnection under the given code in the given registry and return it."""
    conn = MockTunnelConnection()
    await registry.register(
        code,
        conn,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )
    return conn


# ---------------------------------------------------------------------------
# get_client_ip unit tests
# ---------------------------------------------------------------------------


def test_get_client_ip_from_x_forwarded_for() -> None:
    """get_client_ip extracts the first IP from X-Forwarded-For header."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"203.0.113.5, 10.0.0.1")],
    }
    request = Request(scope)
    assert get_client_ip(request) == "203.0.113.5"


def test_get_client_ip_falls_back_to_client_host() -> None:
    """get_client_ip falls back to request.client.host when no X-Forwarded-For."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("192.168.1.100", 54321),
    }
    request = Request(scope)
    assert get_client_ip(request) == "192.168.1.100"


def test_get_client_ip_raises_without_any_source() -> None:
    """get_client_ip raises ValueError when no IP source is available."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    request = Request(scope)
    with pytest.raises(ValueError, match="Cannot determine client IP"):
        get_client_ip(request)


# ---------------------------------------------------------------------------
# Proxy rate limit integration tests
# ---------------------------------------------------------------------------


async def test_proxy_returns_200_under_rate_limit() -> None:
    """First request to proxy returns 200 (not rate limited)."""
    app, registry = await _make_rate_limited_app("5/minute")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_mock_connection(registry, "testcode")
        response = await client.get("/m/testcode/")
    assert response.status_code == 200
    await registry.close()


async def test_proxy_returns_429_after_exceeding_rate_limit() -> None:
    """After exceeding the rate limit, proxy returns 429 with Retry-After header."""
    app, registry = await _make_rate_limited_app("2/minute")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_mock_connection(registry, "testcode")
        # Send requests up to the limit
        for _ in range(2):
            resp = await client.get("/m/testcode/path")
            assert resp.status_code == 200

        # The next request should be rate limited
        resp = await client.get("/m/testcode/path")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers
    await registry.close()


# ---------------------------------------------------------------------------
# 429 response format tests (HTML vs JSON)
# ---------------------------------------------------------------------------


async def test_429_browser_gets_html() -> None:
    """Browser (Accept: text/html) receives styled HTML 429 page."""
    app, registry = await _make_rate_limited_app("1/minute")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_mock_connection(registry, "testcode")
        # Exhaust the rate limit
        await client.get("/m/testcode/path")
        # This should be 429
        resp = await client.get(
            "/m/testcode/path",
            headers={"accept": "text/html"},
        )

    assert resp.status_code == 429
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Too Many Requests" in resp.text
    assert "retry-after" in resp.headers
    await registry.close()


async def test_429_api_gets_json() -> None:
    """API client (Accept: application/json) receives JSON 429 response."""
    app, registry = await _make_rate_limited_app("1/minute")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register_mock_connection(registry, "testcode")
        # Exhaust the rate limit
        await client.get("/m/testcode/path")
        # This should be 429
        resp = await client.get(
            "/m/testcode/path",
            headers={"accept": "application/json"},
        )

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"] == "Rate limit exceeded"
    assert "retry_after" in body
    assert "retry-after" in resp.headers
    await registry.close()


# ---------------------------------------------------------------------------
# Mount registration rate limit tests (uses limits library directly)
# ---------------------------------------------------------------------------


async def _make_mount_reg_rate_app(mount_reg_rate: str):
    """Create a relay app with a specific mount registration rate limit.

    Each app instance has its own mount-registration rate limiter on
    ``app.state.relay.mount_reg_limiter``, so no cross-test reset is needed.
    Creates an in-memory SqliteMountRegistry since ASGIWebSocketTransport
    does not trigger lifespan.

    Returns:
        Tuple of (app, registry) — caller should close registry when done.
    """
    with patch.dict(os.environ, {
        "RELAY_MOUNT_REG_RATE": mount_reg_rate,
        "RELAY_DB_PATH": ":memory:",
    }):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    return app, registry


async def _ws_recv_first_message(app, path: str) -> dict:
    """Connect to agent WS, receive first message, return parsed JSON."""
    transport = ASGIWebSocketTransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with aconnect_ws(
            f"http://testserver{path}",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            await ws.send_text(
                json.dumps(
                    {
                        "type": "agent_auth",
                        "token": None,
                        "access_mode": "open",
                        "has_password": False,
                        "allowlist": [],
                    }
                )
            )
            raw = await ws.receive_text()
            return json.loads(raw)


async def test_mount_reg_under_rate_limit_succeeds() -> None:
    """Mount registrations under the rate limit all succeed."""
    app, registry = await _make_mount_reg_rate_app("2/minute")
    msg1 = await _ws_recv_first_message(app, "/agent/ws")
    assert msg1["type"] == "mount_registered"
    msg2 = await _ws_recv_first_message(app, "/agent/ws")
    assert msg2["type"] == "mount_registered"
    await registry.close()


async def test_mount_reg_over_rate_limit_rejected() -> None:
    """Mount registration exceeding the rate limit returns error with retry_after."""
    app, registry = await _make_mount_reg_rate_app("2/minute")
    # Two successful
    await _ws_recv_first_message(app, "/agent/ws")
    await _ws_recv_first_message(app, "/agent/ws")
    # Third should be rate limited
    msg = await _ws_recv_first_message(app, "/agent/ws")
    assert msg["type"] == "error"
    assert "Rate limit exceeded" in msg["error"]
    assert "retry_after" in msg
    await registry.close()
