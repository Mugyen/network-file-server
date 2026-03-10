"""Tests for WebSocket connection manager and endpoint."""

import tempfile
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient

from server.app.config import create_default_config, set_server_config
from server.app.main import create_app
from server.app.models.enums import DeviceType
from server.app.services.connection_manager import ConnectionManager, parse_device_type


def _create_configured_app() -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with minimal config for WS integration tests."""
    tmpdir = tempfile.mkdtemp()
    set_server_config(create_default_config(shared_folder=Path(tmpdir), port=8000))
    return create_app()


# --- ConnectionManager unit tests ---


@pytest.mark.asyncio
async def test_manager_connect_adds_websocket() -> None:
    """connect() adds websocket to active_connections keyed by device_id."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice Phone", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    assert "dev-1" in mgr.active_connections
    assert mgr.active_connections["dev-1"] is ws
    ws.accept.assert_awaited_once()


@pytest.mark.asyncio
async def test_manager_disconnect_removes_device() -> None:
    """disconnect() removes device from active_connections and devices."""
    mgr = ConnectionManager()
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice Phone", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    mgr.disconnect("dev-1")
    assert "dev-1" not in mgr.active_connections
    assert "dev-1" not in mgr.devices


@pytest.mark.asyncio
async def test_manager_broadcast_excludes_device() -> None:
    """broadcast() sends to all except excluded device_id."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1, "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    await mgr.connect(ws2, "dev-2", "Bob", "192.168.1.11", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)")

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
    await mgr.connect(ws_good, "dev-good", "Good", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    await mgr.connect(ws_dead, "dev-dead", "Dead", "192.168.1.11", "Mozilla/5.0 (Windows NT 10.0)")

    await mgr.broadcast_all({"type": "test"})

    assert "dev-dead" not in mgr.active_connections
    assert "dev-good" in mgr.active_connections


@pytest.mark.asyncio
async def test_manager_device_count() -> None:
    """device_count() returns correct count."""
    mgr = ConnectionManager()
    assert mgr.device_count() == 0
    ws = AsyncMock()
    await mgr.connect(ws, "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    assert mgr.device_count() == 1
    await mgr.connect(AsyncMock(), "dev-2", "Bob", "192.168.1.11", "Mozilla/5.0 (Windows NT 10.0)")
    assert mgr.device_count() == 2
    mgr.disconnect("dev-1")
    assert mgr.device_count() == 1


# --- parse_device_type unit tests ---


def test_parse_device_type_iphone() -> None:
    """iPhone User-Agent classified as PHONE."""
    assert parse_device_type("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)") == DeviceType.PHONE


def test_parse_device_type_android() -> None:
    """Android User-Agent classified as PHONE."""
    assert parse_device_type("Mozilla/5.0 (Linux; Android 13; Pixel 7)") == DeviceType.PHONE


def test_parse_device_type_mobile_keyword() -> None:
    """UA with Mobile keyword classified as PHONE."""
    assert parse_device_type("Mozilla/5.0 Mobile Safari/537.36") == DeviceType.PHONE


def test_parse_device_type_ipad() -> None:
    """iPad User-Agent classified as TABLET."""
    assert parse_device_type("Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X)") == DeviceType.TABLET


def test_parse_device_type_desktop() -> None:
    """Windows desktop User-Agent classified as DESKTOP."""
    assert parse_device_type("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == DeviceType.DESKTOP


def test_parse_device_type_empty_string() -> None:
    """Empty string defaults to DESKTOP."""
    assert parse_device_type("") == DeviceType.DESKTOP


@pytest.mark.asyncio
async def test_manager_get_device_list() -> None:
    """get_device_list() returns list of dicts for all connected devices."""
    mgr = ConnectionManager()
    await mgr.connect(AsyncMock(), "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    await mgr.connect(AsyncMock(), "dev-2", "Bob", "192.168.1.11", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)")

    device_list = mgr.get_device_list()
    assert len(device_list) == 2
    ids = {d["device_id"] for d in device_list}
    assert ids == {"dev-1", "dev-2"}
    for d in device_list:
        assert "device_name" in d
        assert "ip_address" in d
        assert "device_type" in d
        assert "connected_at" in d


@pytest.mark.asyncio
async def test_manager_connect_stores_device_info() -> None:
    """connect() stores DeviceInfo with correct ip_address, device_type, and ISO connected_at."""
    mgr = ConnectionManager()
    await mgr.connect(AsyncMock(), "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0)")

    info = mgr.devices["dev-1"]
    assert info.ip_address == "192.168.1.10"
    assert info.device_type == "phone"
    assert "T" in info.connected_at  # ISO format contains T


@pytest.mark.asyncio
async def test_manager_get_device_name_from_devices() -> None:
    """get_device_name() returns name from devices dict."""
    mgr = ConnectionManager()
    await mgr.connect(AsyncMock(), "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    assert mgr.get_device_name("dev-1") == "Alice"


# --- WebSocket endpoint integration tests ---


def test_ws_connect_receives_device_count() -> None:
    """WebSocket at /ws accepts connection and sends device_list then device_count."""
    app = _create_configured_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=TestDevice") as ws:
        # First message is device_list
        device_list_msg = ws.receive_json()
        assert device_list_msg["type"] == "device_list"
        assert "devices" in device_list_msg
        assert "your_device_id" in device_list_msg
        # Then device_count
        data = ws.receive_json()
        assert data["type"] == "device_count"
        assert data["count"] == 1


def test_ws_two_clients_toast_on_connect() -> None:
    """Second client connecting triggers device_connected toast on first."""
    app = _create_configured_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=Alice") as ws1:
        # Consume Alice's device_list and device_count
        ws1.receive_json()  # device_list
        ws1.receive_json()  # device_count
        with client.websocket_connect("/ws?device_name=Bob") as ws2:
            # Alice should get a toast about Bob connecting
            toast_msg = ws1.receive_json()
            assert toast_msg["type"] == "toast"
            assert toast_msg["toast_type"] == "device_connected"
            assert "Bob" in toast_msg["message"]
            assert "device_info" in toast_msg
            # Then Alice gets updated device_count
            count_msg = ws1.receive_json()
            assert count_msg["type"] == "device_count"
            assert count_msg["count"] == 2
            # Bob gets device_list then device_count
            bob_list = ws2.receive_json()
            assert bob_list["type"] == "device_list"
            bob_count = ws2.receive_json()
            assert bob_count["type"] == "device_count"
            assert bob_count["count"] == 2


@pytest.mark.asyncio
async def test_manager_disconnect_broadcasts_toast() -> None:
    """Disconnecting broadcasts toast + updated count via manager directly."""
    mgr = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    await mgr.connect(ws1, "dev-1", "Alice", "192.168.1.10", "Mozilla/5.0 (Windows NT 10.0)")
    await mgr.connect(ws2, "dev-2", "Bob", "192.168.1.11", "Mozilla/5.0 (Windows NT 10.0)")

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
    with tempfile.TemporaryDirectory() as tmpdir:
        set_server_config(create_default_config(shared_folder=Path(tmpdir), port=8000))
        app = create_app()
        client = TestClient(app)
        with client.websocket_connect("/ws?device_name=Watcher") as ws:
            ws.receive_json()  # device_list
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


def test_device_list_on_connect() -> None:
    """New client receives device_list containing self with matching your_device_id."""
    app = _create_configured_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=Solo") as ws:
        device_list_msg = ws.receive_json()
        assert device_list_msg["type"] == "device_list"
        devices = device_list_msg["devices"]
        assert len(devices) == 1
        assert devices[0]["device_name"] == "Solo"
        assert device_list_msg["your_device_id"] == devices[0]["device_id"]


def test_device_connected_toast_includes_info() -> None:
    """Connect toast received by other clients includes device_info dict."""
    app = _create_configured_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=Alice") as ws1:
        ws1.receive_json()  # device_list
        ws1.receive_json()  # device_count
        with client.websocket_connect("/ws?device_name=Bob") as ws2:
            toast = ws1.receive_json()
            assert toast["type"] == "toast"
            assert toast["toast_type"] == "device_connected"
            info = toast["device_info"]
            assert info["device_name"] == "Bob"
            assert "ip_address" in info
            assert "device_type" in info


def test_device_disconnected_toast_includes_id() -> None:
    """Disconnect toast includes device_id of the disconnected device."""
    app = _create_configured_app()
    client = TestClient(app)
    with client.websocket_connect("/ws?device_name=Alice") as ws1:
        ws1.receive_json()  # device_list
        ws1.receive_json()  # device_count
        with client.websocket_connect("/ws?device_name=Bob") as ws2:
            ws1.receive_json()  # Bob's connect toast
            ws1.receive_json()  # device_count update
            ws2.receive_json()  # Bob's device_list
            ws2.receive_json()  # Bob's device_count
        # Bob disconnects - Alice gets disconnect toast
        toast = ws1.receive_json()
        assert toast["type"] == "toast"
        assert toast["toast_type"] == "device_disconnected"
        assert "device_id" in toast
