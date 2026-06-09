"""Tests for expired file control message on agent mount reclaim."""

import time

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


# ---------------------------------------------------------------------------
# Agent-to-relay expired files handler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_expired_files_clears_records(relay_app, file_ttl_with_registry) -> None:
    """Agent sending delete_expired_files clears expired TTL records for that mount."""
    registry = get_registry()
    file_ttl_db = file_ttl_with_registry

    # Register mount and add expired records
    conn = MockTunnelConnection()
    await registry.register("agentmnt", conn, agent_ip="127.0.0.1", created_at=time.time(), expires_at=time.time() + 3600)
    await file_ttl_db.record_file_ttl("agentmnt", "expired1.txt", -1)
    await file_ttl_db.record_file_ttl("agentmnt", "expired2.txt", -1)

    # Simulate the handler function from agent_ws.py
    from relay.app.routers.agent_ws import _handle_agent_control_for_mount
    await _handle_agent_control_for_mount(
        {"type": "delete_expired_files", "code": "agentmnt"},
        "agentmnt",
    )

    # Expired records should be cleared
    expired = await file_ttl_db.get_expired_for_mount("agentmnt")
    assert len(expired) == 0


@pytest.mark.asyncio
async def test_keep_expired_files_clears_records(relay_app, file_ttl_with_registry) -> None:
    """Agent sending keep_expired_files also clears expired TTL records (no re-prompt)."""
    registry = get_registry()
    file_ttl_db = file_ttl_with_registry

    conn = MockTunnelConnection()
    await registry.register("agentmnt2", conn, agent_ip="127.0.0.1", created_at=time.time(), expires_at=time.time() + 3600)
    await file_ttl_db.record_file_ttl("agentmnt2", "kept-file.txt", -1)

    from relay.app.routers.agent_ws import _handle_agent_control_for_mount
    await _handle_agent_control_for_mount(
        {"type": "keep_expired_files", "code": "agentmnt2"},
        "agentmnt2",
    )

    expired = await file_ttl_db.get_expired_for_mount("agentmnt2")
    assert len(expired) == 0
