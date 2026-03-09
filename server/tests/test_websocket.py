"""Tests for WebSocket connection manager and endpoint."""

from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient

from server.app.main import create_app
from server.app.services.connection_manager import ConnectionManager


# --- ConnectionManager unit tests ---


@pytest.mark.asyncio
async def test_manager_connect_adds_websocket() -> None:
    """connect() adds websocket to active_connections keyed by device_id."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice Phone")
    assert "dev-1" in mgr.active_connections
    assert mgr.active_connections["dev-1"] is ws
    ws.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_disconnect_removes_device() -> None:
    """disconnect() removes device from active_connections and device_names."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice Phone")
    mgr.disconnect("dev-1")
    assert "dev-1" not in mgr.active_connections
    assert "dev-1" not in mgr.device_names


@pytest.mark.asyncio
async def test_manager_broadcast_excludes_device() -> None:
    """broadcast() sends to all except excluded device_id."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1, "dev-1", "Alice")
    await mgr.connect(ws2, "dev-2", "Bob")

    msg = {"type": "toast", "message": "hello"}
    await mgr.broadcast(msg, "dev-1")

    ws1.send_json.assert_not_awaited()
    ws2.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_manager_broadcast_removes_dead_connections() -> None:
    """broadcast() removes connections that raise on send_json."""
    mgr = ConnectionManager()
    ws_good = AsyncMock()
    ws_dead = AsyncMock()
    ws_dead.send_json.side_effect = RuntimeError("connection closed")
    await mgr.connect(ws_good, "dev-good", "Good")
    await mgr.connect(ws_dead, "dev-dead", "Dead")

    await mgr.broadcast_all({"type": "test"})

    assert "dev-dead" not in mgr.active_connections
    assert "dev-good" in mgr.active_connections


@pytest.mark.asyncio
async def test_manager_device_count() -> None:
    """device_count() returns correct count."""
    mgr = ConnectionManager()
    assert mgr.device_count() == 0
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice")
    assert mgr.device_count() == 1
    await mgr.connect(AsyncMock(), "dev-2", "Bob")
    assert mgr.device_count() == 2
    mgr.disconnect("dev-1")
    assert mgr.device_count() == 1


# --- WebSocket endpoint integration tests ---


def test_ws_connect_receives_device_count() -> None:
    """WebSocket at /ws accepts connection and sends device_count."""
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=TestDevice") as ws:
        data = ws.receive_json()
        assert data["type"] == "device_count"
        assert data["count"] == 1


def test_ws_two_clients_toast_on_connect() -> None:
    """Second client connecting triggers device_connected toast on first."""
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=Alice") as ws1:
        # Consume Alice's own device_count
        ws1.receive_json()
        with client.websocket_connect("/ws?device_name=Bob") as ws2:
            # Alice should get a toast about Bob connecting
            toast_msg = ws1.receive_json()
            assert toast_msg["type"] == "toast"
            assert toast_msg["toast_type"] == "device_connected"
            assert "Bob" in toast_msg["message"]
            # Then Alice gets updated device_count
            count_msg = ws1.receive_json()
            assert count_msg["type"] == "device_count"
            assert count_msg["count"] == 2
            # Bob gets device_count
            bob_count = ws2.receive_json()
            assert bob_count["type"] == "device_count"
            assert bob_count["count"] == 2


@pytest.mark.asyncio
async def test_manager_disconnect_broadcasts_toast() -> None:
    """Disconnecting broadcasts toast + updated count via manager directly."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1, "dev-1", "Alice")
    await mgr.connect(ws2, "dev-2", "Bob")

    # Simulate Bob disconnecting
    mgr.disconnect("dev-2")
    toast = {"type": "toast", "toast_type": "device_disconnected", "message": "Bob disconnected"}
    await mgr.broadcast_all(toast)
    count = {"type": "device_count", "count": mgr.device_count()}
    await mgr.broadcast_all(count)

    # Alice should have received both messages
    calls = [c.args[0] for c in ws1.send_json.call_args_list]
    assert any(m.get("toast_type") == "device_disconnected" for m in calls)
    assert any(m.get("type") == "device_count" and m.get("count") == 1 for m in calls)


def test_upload_broadcasts_toast_to_ws_clients() -> None:
    """File upload broadcasts file_uploaded toast to WS connections."""
    import tempfile
    app = create_app()
    with tempfile.TemporaryDirectory() as tmpdir:
        from server.app.config import set_server_config, ServerConfig
        set_server_config(ServerConfig(shared_folder=Path(tmpdir), port=8000))

        client = TestClient(app)
        with client.websocket_connect("/ws?device_name=Watcher") as ws:
            ws.receive_json()  # device_count

            response = client.post(
                "/api/files/upload?path=",
                files=[("files", ("test.txt", b"hello", "text/plain"))],
            )
            assert response.status_code == 200

            toast_msg = ws.receive_json()
            assert toast_msg["type"] == "toast"
            assert toast_msg["toast_type"] == "file_uploaded"
            assert "1 file" in toast_msg["message"]
