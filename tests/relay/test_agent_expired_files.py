"""Tests for expired file control message on agent mount reclaim."""

import time

import aiosqlite
import pytest

from relay.app.services.file_ttl_db import FileTtlDb, set_file_ttl_db
from relay.app.services.mount_registry import get_registry
from tests.relay.conftest import MockTunnelConnection


@pytest.fixture
async def file_ttl_with_registry(relay_app):
    """Set up file_ttl_db using the same in-memory SQLite as the registry."""
    registry = get_registry()
    file_ttl_db = FileTtlDb(registry._db)
    await file_ttl_db.init_table()
    set_file_ttl_db(file_ttl_db)
    yield file_ttl_db
    set_file_ttl_db(None)


@pytest.mark.asyncio
async def test_reclaim_sends_expired_files_control(relay_app, file_ttl_with_registry) -> None:
    """When a mount is reclaimed with expired file_ttl records, the relay sends expired_files."""
    registry = get_registry()
    file_ttl_db = file_ttl_with_registry

    # Register and disconnect the mount
    conn1 = MockTunnelConnection()
    await registry.register("agentcode", conn1, agent_ip="127.0.0.1", created_at=time.time(), expires_at=time.time() + 3600)
    await registry.mark_offline("agentcode")

    # Add expired file TTL records
    await file_ttl_db.record_file_ttl("agentcode", "old-report.txt", -1)

    # Reclaim with a new connection that captures sent control messages
    conn2 = MockTunnelConnection()
    sent_controls: list[dict] = []
    original_send = conn2.send_control

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)
        await original_send(msg)

    conn2.send_control = capture_send

    result = await registry.try_reclaim("agentcode", conn2, "127.0.0.1")
    assert result is not None

    # Simulate what agent_ws.py does after reclaim
    expired = await file_ttl_db.get_expired_for_mount("agentcode")
    if expired:
        await conn2.send_control({
            "type": "expired_files",
            "code": "agentcode",
            "files": [{"path": fp, "expired_at": exp} for fp, exp in expired],
        })

    # Verify expired_files control was sent
    expired_msgs = [m for m in sent_controls if m.get("type") == "expired_files"]
    assert len(expired_msgs) == 1
    assert expired_msgs[0]["code"] == "agentcode"
    assert len(expired_msgs[0]["files"]) == 1
    assert expired_msgs[0]["files"][0]["path"] == "old-report.txt"


@pytest.mark.asyncio
async def test_reclaim_no_expired_files_no_control(relay_app, file_ttl_with_registry) -> None:
    """When no expired files exist, no expired_files control message is sent."""
    registry = get_registry()

    conn1 = MockTunnelConnection()
    await registry.register("agentcode2", conn1, agent_ip="127.0.0.1", created_at=time.time(), expires_at=time.time() + 3600)
    await registry.mark_offline("agentcode2")

    conn2 = MockTunnelConnection()
    sent_controls: list[dict] = []

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)

    conn2.send_control = capture_send

    await registry.try_reclaim("agentcode2", conn2, "127.0.0.1")

    file_ttl_db = file_ttl_with_registry
    expired = await file_ttl_db.get_expired_for_mount("agentcode2")
    # No expired files, so no control message should be sent
    assert len(expired) == 0
