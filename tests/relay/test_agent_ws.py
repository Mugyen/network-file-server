"""Tests for the agent WebSocket endpoint — relay-side mount registration protocol."""

import asyncio
import json

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.main import create_relay_app
from relay.app.services.mount_registry import MountRegistry, get_registry, set_registry


pytestmark = pytest.mark.anyio


@pytest.fixture
def agent_ws_app():
    """Create a fresh relay app with a new MountRegistry for each test."""
    app = create_relay_app()
    set_registry(MountRegistry())
    return app


async def _recv_mount_registered(app, path: str) -> dict:
    """Connect to the agent WebSocket endpoint, receive the mount_registered control message.

    Uses httpx_ws ASGIWebSocketTransport to call the ASGI app in-process without
    a real network connection.

    Args:
        app:  ASGI application to connect to.
        path: URL path (including query string) relative to http://testserver.

    Returns:
        Parsed JSON dict from the first text frame (the mount_registered message).
    """
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
            raw = await ws.receive_text()
            return json.loads(raw)


async def test_agent_connects_without_code_receives_mount_registered(agent_ws_app) -> None:
    """Agent connects without code param — relay generates code and sends mount_registered."""
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws")
    assert msg["type"] == "mount_registered"
    assert isinstance(msg["code"], str)
    assert len(msg["code"]) == 8


async def test_agent_connects_without_code_assigns_url_safe_code(agent_ws_app) -> None:
    """The generated code contains only URL-safe base64 characters."""
    import re
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws")
    assigned_code = msg["code"]
    # URL-safe base64 uses [A-Za-z0-9_-]
    assert re.fullmatch(r"[A-Za-z0-9_\-]+", assigned_code) is not None


async def test_agent_connects_with_available_preferred_code_uses_it(agent_ws_app) -> None:
    """Agent connects with ?code=preferred and code is available — relay uses preferred code."""
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws?code=mycode99")
    assert msg["type"] == "mount_registered"
    assert msg["code"] == "mycode99"


async def test_agent_connects_with_occupied_code_generates_new_code(agent_ws_app) -> None:
    """Agent connects with ?code=occupied (already taken) — relay generates a different code."""
    from tests.relay.conftest import MockTunnelConnection
    occupied_conn = MockTunnelConnection()
    get_registry().register("occupied", occupied_conn)

    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws?code=occupied")
    assert msg["type"] == "mount_registered"
    # Must be different from the already-occupied code
    assert msg["code"] != "occupied"
    assert isinstance(msg["code"], str)
    assert len(msg["code"]) == 8


async def test_agent_disconnect_deregisters_mount(agent_ws_app) -> None:
    """On WebSocket disconnect, the mount is removed from the registry."""
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws")
    assigned_code = msg["code"]
    # Give the server a moment for the finally block cleanup to run
    await asyncio.sleep(0.05)
    registry = get_registry()
    assert not registry.has_mount(assigned_code)
