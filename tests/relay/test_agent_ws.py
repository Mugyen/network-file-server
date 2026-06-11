"""Tests for the agent WebSocket endpoint — relay-side mount registration protocol."""

import asyncio
import json
import os
import time
from unittest.mock import patch

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.main import create_relay_app
from tests.relay.conftest import MockTunnelConnection, _setup_in_memory_registry
from tunnel.constants import PROTOCOL_VERSION


pytestmark = pytest.mark.anyio


@pytest.fixture
async def agent_ws_app():
    """Create a fresh relay app with in-memory SQLite registry for each test.

    Manually creates the SqliteMountRegistry because ASGIWebSocketTransport
    does not trigger FastAPI lifespan events. Each app instance has its own
    mount-registration rate limiter on ``app.state.relay.mount_reg_limiter``,
    so no cross-test reset is needed.
    """
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    yield app
    await registry.close()


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
            # Protocol: agent sends exactly one agent_auth frame before the
            # relay replies with mount_registered.
            await ws.send_text(
                json.dumps(
                    {
                        "type": "agent_auth", "protocol_version": PROTOCOL_VERSION,
                        "token": None,
                        "access_mode": "open",
                        "has_password": False,
                        "allowlist": [],
                    }
                )
            )
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
    # Register directly with a different IP to truly occupy the code
    registry = agent_ws_app.state.relay.registry
    conn = MockTunnelConnection()
    await registry.register(
        "occupied",
        conn,
        agent_ip="10.99.99.99",
        created_at=time.time(),
        expires_at=None,
    )

    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws?code=occupied")
    assert msg["type"] == "mount_registered"
    # Must be different from the already-occupied code
    assert msg["code"] != "occupied"
    assert isinstance(msg["code"], str)
    assert len(msg["code"]) == 8


async def test_agent_disconnect_marks_mount_offline(agent_ws_app) -> None:
    """On WebSocket disconnect, the mount is marked OFFLINE (not deleted) from the registry."""
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws")
    assigned_code = msg["code"]
    # Give the server a moment for the finally block cleanup to run
    await asyncio.sleep(0.1)
    registry = agent_ws_app.state.relay.registry
    # Mount should still exist (OFFLINE) because we use mark_offline instead of deregister
    assert await registry.has_mount(assigned_code)


async def test_mount_registered_includes_reclaimed_field(agent_ws_app) -> None:
    """mount_registered message includes reclaimed=False for new mounts."""
    msg = await _recv_mount_registered(agent_ws_app, "/agent/ws")
    assert msg["type"] == "mount_registered"
    assert msg["reclaimed"] is False
    assert msg["remaining_ttl"] is None


async def test_agent_reclaims_offline_mount_same_ip(agent_ws_app) -> None:
    """Agent reconnecting with same code from same IP reclaims OFFLINE mount."""
    # First connection: register a mount
    msg1 = await _recv_mount_registered(agent_ws_app, "/agent/ws?code=reclaim1&ttl=7200")
    assert msg1["code"] == "reclaim1"
    assert msg1["reclaimed"] is False

    # Wait for disconnect -> mark_offline
    await asyncio.sleep(0.1)

    # Second connection: reconnect with same code from same IP
    msg2 = await _recv_mount_registered(agent_ws_app, "/agent/ws?code=reclaim1")
    assert msg2["code"] == "reclaim1"
    assert msg2["reclaimed"] is True
    assert msg2["remaining_ttl"] is not None
    assert msg2["remaining_ttl"] > 0


async def test_version_mismatch_rejected(agent_ws_app) -> None:
    """An agent with a skewed protocol_version is refused before registration."""
    transport = ASGIWebSocketTransport(app=agent_ws_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with aconnect_ws(
            "http://testserver/agent/ws",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            await ws.send_text(json.dumps({
                "type": "agent_auth", "protocol_version": PROTOCOL_VERSION + 1,
                "token": None, "access_mode": "open",
                "has_password": False, "allowlist": [],
            }))
            raw = await ws.receive_text()
            msg = json.loads(raw)
    assert msg["type"] == "error"
    assert "protocol version mismatch" in msg["error"]


async def test_missing_version_rejected(agent_ws_app) -> None:
    """An agent omitting protocol_version (pre-versioning) is refused."""
    transport = ASGIWebSocketTransport(app=agent_ws_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with aconnect_ws(
            "http://testserver/agent/ws",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            await ws.send_text(json.dumps({
                "type": "agent_auth",
                "token": None, "access_mode": "open",
                "has_password": False, "allowlist": [],
            }))
            raw = await ws.receive_text()
            msg = json.loads(raw)
    assert msg["type"] == "error"
    assert "protocol version mismatch" in msg["error"]
