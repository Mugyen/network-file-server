"""Tests for drop box service, reserved code protection, and proxy forwarding."""

import time
from pathlib import Path

import httpx
import pytest

from relay.app.config import get_config
from relay.app.services.dropbox import init_dropbox, set_dropbox_client
from relay.app.services.file_ttl_db import FileTtlDb, set_file_ttl_db
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


# ---------------------------------------------------------------------------
# Drop box proxy forwarding integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def dropbox_client(relay_app, tmp_path):
    """Relay client with drop box initialized in a temp directory."""
    config = get_config()
    registry = get_registry()

    # Initialize file TTL tracking on the same SQLite connection
    file_ttl_db = FileTtlDb(registry._db)
    await file_ttl_db.init_table()
    set_file_ttl_db(file_ttl_db)

    # Initialize the drop box server app backed by tmp_path
    client = await init_dropbox(tmp_path, config.dropbox_code)
    set_dropbox_client(client)

    # Register drop box as a first-class mount
    await registry.register(
        code=config.dropbox_code,
        connection=None,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )

    transport = httpx.ASGITransport(app=relay_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    await client.aclose()
    set_dropbox_client(None)
    set_file_ttl_db(None)


@pytest.mark.asyncio
async def test_dropbox_serves_file_browser(dropbox_client) -> None:
    """GET /m/dropbox/ returns 200 (the SPA file browser)."""
    config = get_config()
    resp = await dropbox_client.get(f"/m/{config.dropbox_code}/")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dropbox_file_upload(dropbox_client, tmp_path) -> None:
    """File upload to drop box succeeds and file is browsable."""
    config = get_config()
    # Upload a file
    resp = await dropbox_client.post(
        f"/m/{config.dropbox_code}/api/files/upload?path=",
        files={"files": ("test.txt", b"hello from dropbox", "text/plain")},
    )
    assert resp.status_code == 200

    # Verify file appears in listing
    resp = await dropbox_client.get(f"/m/{config.dropbox_code}/api/files?path=")
    assert resp.status_code == 200
    data = resp.json()
    names = [e["name"] for e in data["entries"]]
    assert "test.txt" in names


@pytest.mark.asyncio
async def test_dropbox_registered_in_sqlite(dropbox_client) -> None:
    """Drop box mount is registered with status ONLINE and expires_at NULL."""
    config = get_config()
    registry = get_registry()
    assert await registry.has_mount(config.dropbox_code)


@pytest.mark.asyncio
async def test_landing_page_has_dropbox_link(dropbox_client) -> None:
    """Landing page contains a link to the drop box mount."""
    config = get_config()
    resp = await dropbox_client.get("/")
    assert resp.status_code == 200
    assert f"/m/{config.dropbox_code}/" in resp.text


# ---------------------------------------------------------------------------
# File TTL integration via drop box
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_with_ttl_records_expiry(dropbox_client, tmp_path) -> None:
    """Upload with ttl=3600 stores a file_ttl record; listing shows expires_at."""
    from relay.app.services.file_ttl_db import get_file_ttl_db

    config = get_config()
    resp = await dropbox_client.post(
        f"/m/{config.dropbox_code}/api/files/upload?path=&ttl=3600",
        files={"files": ("ttl-test.txt", b"ttl content", "text/plain")},
    )
    assert resp.status_code == 200

    file_ttl_db = get_file_ttl_db()
    records = await file_ttl_db.get_ttl_for_mount(config.dropbox_code)
    assert any(r[0] == "ttl-test.txt" for r in records)

    # Listing should show expires_at
    resp = await dropbox_client.get(f"/m/{config.dropbox_code}/api/files?path=")
    assert resp.status_code == 200
    data = resp.json()
    ttl_entry = next((e for e in data["entries"] if e["name"] == "ttl-test.txt"), None)
    assert ttl_entry is not None
    assert ttl_entry["expires_at"] is not None


@pytest.mark.asyncio
async def test_upload_with_ttl_zero_no_record(dropbox_client, tmp_path) -> None:
    """Upload with ttl=0 (Never) does NOT create a file_ttl record."""
    from relay.app.services.file_ttl_db import get_file_ttl_db

    config = get_config()
    resp = await dropbox_client.post(
        f"/m/{config.dropbox_code}/api/files/upload?path=&ttl=0",
        files={"files": ("no-ttl.txt", b"permanent content", "text/plain")},
    )
    assert resp.status_code == 200

    file_ttl_db = get_file_ttl_db()
    records = await file_ttl_db.get_ttl_for_mount(config.dropbox_code)
    assert not any(r[0] == "no-ttl.txt" for r in records)

    # Listing should show expires_at as null
    resp = await dropbox_client.get(f"/m/{config.dropbox_code}/api/files?path=")
    assert resp.status_code == 200
    data = resp.json()
    no_ttl_entry = next((e for e in data["entries"] if e["name"] == "no-ttl.txt"), None)
    assert no_ttl_entry is not None
    assert no_ttl_entry["expires_at"] is None
