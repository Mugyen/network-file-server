"""Tests for SlowAPI rate limiting on proxy requests and 429 error handling."""

import os
import time
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient

from relay.app.config import set_config
from relay.app.main import create_relay_app
from relay.app.rate_limit import get_client_ip
from relay.app.services.mount_registry import MountRegistry, get_registry, set_registry
from tests.relay.conftest import MockTunnelConnection


pytestmark = pytest.mark.anyio


def _make_rate_limited_app(proxy_rate: str):
    """Create a relay app with a tight proxy rate limit for testing.

    Each test gets a fresh app and limiter to avoid cross-test state leakage.
    """
    with patch.dict(os.environ, {"RELAY_PROXY_REQUEST_RATE": proxy_rate}):
        app = create_relay_app()
    set_registry(MountRegistry())
    return app


def _register_mock_connection(code: str) -> MockTunnelConnection:
    """Register a MockTunnelConnection under the given code and return it."""
    conn = MockTunnelConnection()
    get_registry().register(
        code,
        conn,
        agent_ip="127.0.0.1",
        created_at=time.monotonic(),
        expires_at=None,
    )
    return conn


# ---------------------------------------------------------------------------
# get_client_ip unit tests
# ---------------------------------------------------------------------------


def test_get_client_ip_from_x_forwarded_for() -> None:
    """get_client_ip extracts the first IP from X-Forwarded-For header."""
    from starlette.requests import Request
    from starlette.datastructures import Headers

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
    app = _make_rate_limited_app("5/minute")
    _register_mock_connection("testcode")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/m/testcode/")
    assert response.status_code == 200


async def test_proxy_returns_429_after_exceeding_rate_limit() -> None:
    """After exceeding the rate limit, proxy returns 429 with Retry-After header."""
    app = _make_rate_limited_app("2/minute")
    _register_mock_connection("testcode")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Send requests up to the limit
        for _ in range(2):
            resp = await client.get("/m/testcode/path")
            assert resp.status_code == 200

        # The next request should be rate limited
        resp = await client.get("/m/testcode/path")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers


# ---------------------------------------------------------------------------
# 429 response format tests (HTML vs JSON)
# ---------------------------------------------------------------------------


async def test_429_browser_gets_html() -> None:
    """Browser (Accept: text/html) receives styled HTML 429 page."""
    app = _make_rate_limited_app("1/minute")
    _register_mock_connection("testcode")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
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


async def test_429_api_gets_json() -> None:
    """API client (Accept: application/json) receives JSON 429 response."""
    app = _make_rate_limited_app("1/minute")
    _register_mock_connection("testcode")

    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
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
