"""Tests for drop box service, reserved code protection, and proxy forwarding."""

import time

import httpx
import pytest

from relay.app.config import get_config
from relay.app.services.mount_registry import get_registry
from tests.relay.conftest import MockTunnelConnection, _setup_in_memory_registry


# ---------------------------------------------------------------------------
# Reserved code guard in agent_ws.py
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reserved_code_rejected_via_ws(relay_app) -> None:
    """Agent WS rejects registration with reserved dropbox code (1008 close)."""
    from starlette.testclient import TestClient

    # Use TestClient sync WS for simplicity
    client = TestClient(relay_app)
    config = get_config()

    with client.websocket_connect(f"/agent/ws?code={config.dropbox_code}") as ws:
        data = ws.receive_json()
        assert data["type"] == "error"
        assert "Reserved" in data["error"]


# ---------------------------------------------------------------------------
# SqliteMountRegistry.register() with connection=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_with_none_connection(relay_app) -> None:
    """Registry accepts connection=None for local mounts."""
    registry = get_registry()
    await registry.register(
        code="local-mount",
        connection=None,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )
    assert await registry.has_mount("local-mount")


@pytest.mark.asyncio
async def test_get_connection_raises_for_local_mount(relay_app) -> None:
    """get_connection() raises RuntimeError for a code registered with connection=None."""
    registry = get_registry()
    await registry.register(
        code="local-mount2",
        connection=None,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )
    with pytest.raises(RuntimeError, match="no tunnel connection"):
        await registry.get_connection("local-mount2")
