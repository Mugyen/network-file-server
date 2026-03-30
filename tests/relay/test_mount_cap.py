"""Tests for per-IP mount cap enforcement on the agent WebSocket endpoint."""

import json
import os
import time
from unittest.mock import patch

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.enums import MountStatus
from relay.app.main import create_relay_app
from relay.app.services.mount_registry import get_registry, set_registry
from relay.app.services.sqlite_registry import SqliteMountRegistry
from tests.relay.conftest import MockTunnelConnection, _setup_in_memory_registry


pytestmark = pytest.mark.anyio

# All cap tests use this IP via x-forwarded-for to ensure consistent IP matching
_TEST_IP = "10.0.0.1"


def _make_cap_app(max_mounts_per_ip: int):
    """Create a relay app with a specific mount cap for testing.

    Also resets the module-level mount reg limiter to avoid cross-test pollution.
    """
    with patch.dict(os.environ, {
        "RELAY_MAX_MOUNTS_PER_IP": str(max_mounts_per_ip),
        "RELAY_MOUNT_REG_RATE": "100/hour",
        "RELAY_DB_PATH": ":memory:",
    }):
        app = create_relay_app()
    from relay.app.routers.agent_ws import reset_mount_reg_limiter
    reset_mount_reg_limiter()
    return app


async def _ws_connect_from_ip(app, agent_ip: str, path: str) -> dict:
    """Connect to agent WS with a specific x-forwarded-for IP, return first message.

    Passes the IP via headers on the httpx client to simulate Cloud Run's
    X-Forwarded-For header injection.
    """
    transport = ASGIWebSocketTransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"x-forwarded-for": agent_ip},
    ) as client:
        async with aconnect_ws(
            f"http://testserver{path}",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            raw = await ws.receive_text()
            return json.loads(raw)


async def _prefill_mounts(registry: SqliteMountRegistry, count: int, agent_ip: str) -> None:
    """Register N mock mounts from the given IP."""
    now = time.time()
    for i in range(count):
        conn = MockTunnelConnection()
        await registry.register(
            f"prefill-{i}",
            conn,
            agent_ip=agent_ip,
            created_at=now,
            expires_at=now + 86400,
        )


async def test_5_mounts_from_same_ip_all_succeed() -> None:
    """Registering 5 mounts from the same IP succeeds (at the cap, not over)."""
    app = _make_cap_app(5)
    registry = await _setup_in_memory_registry()
    await _prefill_mounts(registry, 4, _TEST_IP)

    # The 5th mount (via WebSocket from same IP) should succeed
    msg = await _ws_connect_from_ip(app, _TEST_IP, "/agent/ws")
    assert msg["type"] == "mount_registered"
    await registry.close()


async def test_6th_mount_from_same_ip_rejected() -> None:
    """Registering a 6th mount from the same IP is rejected with error."""
    app = _make_cap_app(5)
    registry = await _setup_in_memory_registry()
    await _prefill_mounts(registry, 5, _TEST_IP)

    # The 6th mount from same IP should be rejected
    msg = await _ws_connect_from_ip(app, _TEST_IP, "/agent/ws")
    assert msg["type"] == "error"
    assert "Too many active mounts" in msg["error"]
    assert msg["max"] == 5
    await registry.close()


async def test_different_ip_not_affected_by_cap() -> None:
    """5 mounts from IP A, 1 mount from IP B succeeds (different IP not affected)."""
    app = _make_cap_app(5)
    registry = await _setup_in_memory_registry()
    await _prefill_mounts(registry, 5, _TEST_IP)

    # A different IP should succeed
    msg = await _ws_connect_from_ip(app, "192.168.1.100", "/agent/ws")
    assert msg["type"] == "mount_registered"
    await registry.close()


async def test_expired_mount_frees_cap_slot() -> None:
    """5 mounts from IP A, expire 1, 6th from IP A now succeeds."""
    app = _make_cap_app(5)
    registry = await _setup_in_memory_registry()
    await _prefill_mounts(registry, 5, _TEST_IP)
    # Expire one mount via registry method
    await registry.expire("prefill-0")

    # Now there are 4 active mounts from the IP, so a new one should succeed
    msg = await _ws_connect_from_ip(app, _TEST_IP, "/agent/ws")
    assert msg["type"] == "mount_registered"
    await registry.close()
