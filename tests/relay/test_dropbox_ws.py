"""Tests for drop box WebSocket bridge in mount_proxy.

Verifies that browser WebSocket connections to the drop box mount are bridged
via ASGIWebSocketTransport (not immediately closed), and that messages from
the drop box server app flow through the bridge to the browser.
"""

import asyncio
import json
import time

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.main import create_relay_app
from relay.app.services.mount_registry import set_registry
from relay.app.services.sqlite_registry import SqliteMountRegistry


@pytest.fixture
async def dropbox_relay_app(monkeypatch):
    """Create a relay app with drop box initialized for WS bridge testing.

    Uses in-memory registry and a real server app as the drop box backend.
    """
    monkeypatch.setenv("RELAY_DB_PATH", ":memory:")
    app = create_relay_app()

    registry = await SqliteMountRegistry.create(":memory:")
    set_registry(registry)

    # Register the drop box mount (same as lifespan does)
    from relay.app.config import get_config
    config = get_config()
    await registry.register(
        code=config.dropbox_code,
        connection=None,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )

    # Initialize drop box app and store it
    from pathlib import Path
    import tempfile
    from relay.app.services.dropbox import init_dropbox, set_dropbox_client, set_dropbox_app

    tmpdir = tempfile.mkdtemp()
    client = await init_dropbox(Path(tmpdir), config.dropbox_code)
    set_dropbox_client(client)

    yield app

    await client.aclose()
    set_dropbox_client(None)
    set_dropbox_app(None)
    await registry.close()


@pytest.mark.asyncio
async def test_dropbox_ws_bridge_connects(dropbox_relay_app) -> None:
    """WebSocket connection to drop box mount is NOT immediately closed.

    The connection should stay open (bridged via ASGIWebSocketTransport).
    Before the fix, mount_proxy.py would accept and immediately close
    with code 1000. Now it bridges to the drop box server app.
    """
    from relay.app.config import get_config
    config = get_config()

    async with ASGIWebSocketTransport(app=dropbox_relay_app) as transport:
        async with aconnect_ws(
            f"http://test/m/{config.dropbox_code}/ws?device_name=TestDevice",
            httpx.AsyncClient(transport=transport),
            keepalive_ping_interval_seconds=None,
        ) as ws:
            # If we reach here, the connection was NOT immediately closed.
            # The bridge kept it open, proving the fix works.
            pass


@pytest.mark.asyncio
async def test_dropbox_ws_bridge_receives_initial_messages(dropbox_relay_app) -> None:
    """Browser WS receives initial messages from the drop box server app through the bridge.

    The server app's WS endpoint sends device_count and device_list on connect.
    Receiving these proves the bridge forwards messages from server to browser.
    """
    from relay.app.config import get_config
    config = get_config()

    async with ASGIWebSocketTransport(app=dropbox_relay_app) as transport:
        async with aconnect_ws(
            f"http://test/m/{config.dropbox_code}/ws?device_name=TestDevice",
            httpx.AsyncClient(transport=transport),
            keepalive_ping_interval_seconds=None,
        ) as ws:
            # The server app sends initial messages on WS connect:
            # device_count and device_list. Receive first message with timeout.
            msg_text = await asyncio.wait_for(ws.receive_text(), timeout=2.0)
            data = json.loads(msg_text)
            # Should be one of the expected initial message types
            assert data["type"] in ("device_count", "device_list", "toast")
