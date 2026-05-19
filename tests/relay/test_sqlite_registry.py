"""Tests for SqliteMountRegistry — SQLite-backed mount persistence.

Covers PERS-01 (persistence across reopen), PERS-02 (startup cleanup),
PERS-04 (expired record deletion), plus full CRUD, reclaim, and edge cases.
"""

import time
from pathlib import Path

import pytest

from relay.app.enums import MountStatus
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError
from relay.app.services.sqlite_registry import ReclaimResult, SqliteMountRegistry
from tests.relay.conftest import MockTunnelConnection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> float:
    """Return current wall-clock time for test convenience."""
    return time.time()


async def _make_registry(db_path: str) -> SqliteMountRegistry:
    """Create a fresh SqliteMountRegistry at the given path."""
    return await SqliteMountRegistry.create(db_path)


# ---------------------------------------------------------------------------
# PERS-01: Persistence across close/reopen
# ---------------------------------------------------------------------------


async def test_persistence_across_reopen(tmp_path: Path) -> None:
    """Mount metadata survives close/reopen of the DB file."""
    db_file = str(tmp_path / "mounts.db")
    now = _now()
    conn = MockTunnelConnection()

    reg = await _make_registry(db_file)
    await reg.register("PERSIST1", conn, "10.0.0.1", now, now + 3600)
    await reg.close()

    # Reopen from the same file — startup cleanup marks ONLINE -> OFFLINE
    reg2 = await _make_registry(db_file)
    assert await reg2.has_mount("PERSIST1")

    # Mount should be OFFLINE after startup cleanup
    with pytest.raises(MountOfflineError):
        await reg2.get_connection("PERSIST1")

    # Verify metadata preserved via active_mounts
    mounts = await reg2.active_mounts()
    assert len(mounts) == 1
    assert mounts[0].code == "PERSIST1"
    assert mounts[0].agent_ip == "10.0.0.1"
    assert mounts[0].created_at == now
    assert mounts[0].expires_at == now + 3600
    assert mounts[0].status == MountStatus.OFFLINE
    await reg2.close()


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


async def test_register_stores_mount() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("ABCD1234", conn, "127.0.0.1", _now(), None)
    assert await reg.has_mount("ABCD1234")
    await reg.close()


async def test_register_empty_code_raises_value_error() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    with pytest.raises(ValueError, match="Mount code must not be empty"):
        await reg.register("", conn, "127.0.0.1", _now(), None)
    await reg.close()


async def test_register_overwrites_existing() -> None:
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    now = _now()
    await reg.register("CODE1234", conn1, "127.0.0.1", now, None)
    await reg.register("CODE1234", conn2, "127.0.0.1", now, None)
    retrieved = await reg.get_connection("CODE1234")
    assert retrieved is conn2
    await reg.close()


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------


async def test_get_connection_returns_connection() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("MYCODE12", conn, "127.0.0.1", _now(), None)
    retrieved = await reg.get_connection("MYCODE12")
    assert retrieved is conn
    await reg.close()


async def test_get_connection_unknown_raises_not_found() -> None:
    reg = await _make_registry(":memory:")
    with pytest.raises(MountNotFoundError) as exc_info:
        await reg.get_connection("UNKNOWN1")
    assert exc_info.value.code == "UNKNOWN1"
    await reg.close()


async def test_get_connection_offline_raises_offline_error() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("OFFLINE1", conn, "127.0.0.1", _now(), None)
    await reg.mark_offline("OFFLINE1")
    with pytest.raises(MountOfflineError) as exc_info:
        await reg.get_connection("OFFLINE1")
    assert exc_info.value.code == "OFFLINE1"
    await reg.close()


async def test_get_connection_closed_connection_raises_offline_error() -> None:
    """A registered-but-closed connection is treated as offline.

    Regression: a torn-down agent connection could linger ONLINE (mark_offline
    race-guard no-op under reclaim churn) and get_connection would hand it
    back, causing RuntimeError on the next send to its closed WebSocket.
    """
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("CLOSED01", conn, "127.0.0.1", _now(), None)
    conn.closed = True  # status row stays ONLINE, but the connection is dead
    with pytest.raises(MountOfflineError) as exc_info:
        await reg.get_connection("CLOSED01")
    assert exc_info.value.code == "CLOSED01"
    await reg.close()


async def test_get_connection_expired_raises_expired_error() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("EXPIRED1", conn, "127.0.0.1", _now(), None)
    await reg.expire("EXPIRED1")
    with pytest.raises(MountExpiredError) as exc_info:
        await reg.get_connection("EXPIRED1")
    assert exc_info.value.code == "EXPIRED1"
    await reg.close()


# ---------------------------------------------------------------------------
# deregister
# ---------------------------------------------------------------------------


async def test_deregister_removes_mount() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("DEREG123", conn, "127.0.0.1", _now(), None)
    await reg.deregister("DEREG123")
    assert not await reg.has_mount("DEREG123")
    await reg.close()


async def test_deregister_unknown_raises_not_found() -> None:
    reg = await _make_registry(":memory:")
    with pytest.raises(MountNotFoundError) as exc_info:
        await reg.deregister("NOTHERE1")
    assert exc_info.value.code == "NOTHERE1"
    await reg.close()


async def test_deregister_removes_from_memory_dict() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("MEMRM001", conn, "127.0.0.1", _now(), None)
    await reg.deregister("MEMRM001")
    assert "MEMRM001" not in reg._connections
    await reg.close()


# ---------------------------------------------------------------------------
# mark_offline
# ---------------------------------------------------------------------------


async def test_mark_offline_updates_status() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("MARK0001", conn, "127.0.0.1", _now(), None)
    await reg.mark_offline("MARK0001")

    # Connection should be removed from memory
    assert "MARK0001" not in reg._connections

    # Status should be OFFLINE in SQLite
    with pytest.raises(MountOfflineError):
        await reg.get_connection("MARK0001")
    await reg.close()


async def test_mark_offline_unknown_raises_not_found() -> None:
    reg = await _make_registry(":memory:")
    with pytest.raises(MountNotFoundError):
        await reg.mark_offline("UNKNOWN2")
    await reg.close()


async def test_mark_offline_already_offline_is_noop() -> None:
    """Race guard: mark_offline on already-OFFLINE mount is a no-op."""
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("RACE0001", conn, "127.0.0.1", _now(), None)
    await reg.mark_offline("RACE0001")
    # Second call should not raise
    await reg.mark_offline("RACE0001")
    await reg.close()


async def test_mark_offline_on_expired_is_noop() -> None:
    """mark_offline on EXPIRED mount is a no-op (race guard)."""
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("RACEXP01", conn, "127.0.0.1", _now(), None)
    await reg.expire("RACEXP01")
    # Should not raise or change status
    await reg.mark_offline("RACEXP01")
    with pytest.raises(MountExpiredError):
        await reg.get_connection("RACEXP01")
    await reg.close()


# ---------------------------------------------------------------------------
# expire
# ---------------------------------------------------------------------------


async def test_expire_updates_status() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("EXP_0001", conn, "127.0.0.1", _now(), _now() + 3600)
    await reg.expire("EXP_0001")
    with pytest.raises(MountExpiredError):
        await reg.get_connection("EXP_0001")
    # Record still exists in SQLite
    assert await reg.has_mount("EXP_0001")
    await reg.close()


async def test_expire_removes_connection_from_memory() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("EXP_0002", conn, "127.0.0.1", _now(), None)
    await reg.expire("EXP_0002")
    assert "EXP_0002" not in reg._connections
    await reg.close()


async def test_expire_unknown_raises_not_found() -> None:
    reg = await _make_registry(":memory:")
    with pytest.raises(MountNotFoundError):
        await reg.expire("NOTHERE2")
    await reg.close()


# ---------------------------------------------------------------------------
# has_mount
# ---------------------------------------------------------------------------


async def test_has_mount_false_for_unknown() -> None:
    reg = await _make_registry(":memory:")
    assert not await reg.has_mount("NOTHERE3")
    await reg.close()


async def test_has_mount_true_for_any_status() -> None:
    """has_mount returns True regardless of status (ONLINE, OFFLINE, EXPIRED)."""
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    now = _now()

    await reg.register("HAS_ON01", conn, "127.0.0.1", now, None)
    assert await reg.has_mount("HAS_ON01")

    await reg.mark_offline("HAS_ON01")
    assert await reg.has_mount("HAS_ON01")

    await reg.expire("HAS_ON01")
    assert await reg.has_mount("HAS_ON01")
    await reg.close()


# ---------------------------------------------------------------------------
# count_mounts_by_ip
# ---------------------------------------------------------------------------


async def test_count_mounts_by_ip_correct_count() -> None:
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    await reg.register("IP_A_001", conn1, "10.0.0.1", _now(), None)
    await reg.register("IP_A_002", conn2, "10.0.0.1", _now(), None)
    assert await reg.count_mounts_by_ip("10.0.0.1") == 2
    await reg.close()


async def test_count_mounts_by_ip_zero_for_unknown() -> None:
    reg = await _make_registry(":memory:")
    assert await reg.count_mounts_by_ip("192.168.1.1") == 0
    await reg.close()


async def test_count_mounts_by_ip_excludes_expired() -> None:
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    await reg.register("CEXP0001", conn1, "10.0.0.2", _now(), None)
    await reg.register("CEXP0002", conn2, "10.0.0.2", _now(), None)
    await reg.expire("CEXP0001")
    assert await reg.count_mounts_by_ip("10.0.0.2") == 1
    await reg.close()


# ---------------------------------------------------------------------------
# active_mounts
# ---------------------------------------------------------------------------


async def test_active_mounts_returns_non_expired() -> None:
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    conn3 = MockTunnelConnection()
    now = _now()
    await reg.register("ACT_0001", conn1, "10.0.0.1", now, None)
    await reg.register("ACT_0002", conn2, "10.0.0.1", now, None)
    await reg.register("ACT_0003", conn3, "10.0.0.1", now, None)
    await reg.expire("ACT_0002")

    active = await reg.active_mounts()
    codes = {m.code for m in active}
    assert codes == {"ACT_0001", "ACT_0003"}
    await reg.close()


async def test_active_mounts_connection_none_for_offline() -> None:
    """OFFLINE mounts in active_mounts should have connection=None."""
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    await reg.register("OFFLN001", conn, "127.0.0.1", _now(), None)
    await reg.mark_offline("OFFLN001")

    mounts = await reg.active_mounts()
    assert len(mounts) == 1
    assert mounts[0].connection is None
    await reg.close()


# ---------------------------------------------------------------------------
# PERS-02: Startup cleanup
# ---------------------------------------------------------------------------


async def test_startup_deletes_expired_past_retention(tmp_path: Path) -> None:
    """Startup cleanup deletes expired records older than 6h retention."""
    db_file = str(tmp_path / "mounts.db")
    now = _now()
    reg = await _make_registry(db_file)

    # Create a mount that expired 7 hours ago (beyond 6h retention)
    conn = MockTunnelConnection()
    await reg.register("OLD_EXP1", conn, "10.0.0.1", now - 86400, now - (7 * 3600))
    await reg.expire("OLD_EXP1")
    await reg.close()

    # Reopen — startup cleanup should delete the old expired record
    reg2 = await _make_registry(db_file)
    assert not await reg2.has_mount("OLD_EXP1")
    await reg2.close()


async def test_startup_marks_newly_expired_as_expired(tmp_path: Path) -> None:
    """Startup marks mounts whose expires_at has passed as EXPIRED."""
    db_file = str(tmp_path / "mounts.db")
    now = _now()
    reg = await _make_registry(db_file)

    # Create a mount that expired 1 hour ago (within retention, but should be EXPIRED)
    conn = MockTunnelConnection()
    await reg.register("NEW_EXP1", conn, "10.0.0.1", now - 7200, now - 3600)
    await reg.close()

    # Reopen — startup cleanup should mark it EXPIRED (within retention window)
    reg2 = await _make_registry(db_file)
    assert await reg2.has_mount("NEW_EXP1")
    with pytest.raises(MountExpiredError):
        await reg2.get_connection("NEW_EXP1")
    await reg2.close()


async def test_startup_marks_online_as_offline(tmp_path: Path) -> None:
    """Startup marks all previously-ONLINE mounts as OFFLINE."""
    db_file = str(tmp_path / "mounts.db")
    now = _now()
    reg = await _make_registry(db_file)

    conn = MockTunnelConnection()
    await reg.register("ONLINE01", conn, "10.0.0.1", now, now + 86400)
    await reg.close()

    reg2 = await _make_registry(db_file)
    with pytest.raises(MountOfflineError):
        await reg2.get_connection("ONLINE01")
    await reg2.close()


# ---------------------------------------------------------------------------
# PERS-04: delete_expired_before
# ---------------------------------------------------------------------------


async def test_delete_expired_before_removes_old_records() -> None:
    reg = await _make_registry(":memory:")
    now = _now()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()

    # One expired long ago, one expired recently
    await reg.register("OLD_0001", conn1, "10.0.0.1", now - 86400, now - (7 * 3600))
    await reg.expire("OLD_0001")
    await reg.register("NEW_0001", conn2, "10.0.0.1", now - 3600, now - 1800)
    await reg.expire("NEW_0001")

    # Delete records expired before 2 hours ago
    cutoff = now - (2 * 3600)
    await reg.delete_expired_before(cutoff)

    assert not await reg.has_mount("OLD_0001")
    assert await reg.has_mount("NEW_0001")
    await reg.close()


async def test_delete_expired_before_does_not_touch_non_expired() -> None:
    reg = await _make_registry(":memory:")
    now = _now()
    conn = MockTunnelConnection()

    await reg.register("ACTIVE01", conn, "10.0.0.1", now, now + 3600)
    await reg.delete_expired_before(now)

    assert await reg.has_mount("ACTIVE01")
    await reg.close()


# ---------------------------------------------------------------------------
# try_reclaim
# ---------------------------------------------------------------------------


async def test_try_reclaim_offline_mount_succeeds() -> None:
    reg = await _make_registry(":memory:")
    now = _now()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()

    await reg.register("RECLAIM1", conn1, "10.0.0.1", now, now + 3600)
    await reg.mark_offline("RECLAIM1")

    result = await reg.try_reclaim("RECLAIM1", conn2, "10.0.0.1")
    assert result is not None
    assert isinstance(result, ReclaimResult)
    assert result.remaining_ttl > 0

    # Should be back to ONLINE with new connection
    retrieved = await reg.get_connection("RECLAIM1")
    assert retrieved is conn2
    await reg.close()


async def test_try_reclaim_not_found_returns_none() -> None:
    reg = await _make_registry(":memory:")
    conn = MockTunnelConnection()
    result = await reg.try_reclaim("MISSING1", conn, "10.0.0.1")
    assert result is None
    await reg.close()


async def test_try_reclaim_online_returns_none() -> None:
    """Cannot reclaim an ONLINE mount."""
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    await reg.register("RECL_ON1", conn1, "10.0.0.1", _now(), _now() + 3600)
    result = await reg.try_reclaim("RECL_ON1", conn2, "10.0.0.1")
    assert result is None
    await reg.close()


async def test_try_reclaim_ip_mismatch_returns_none() -> None:
    """Cannot reclaim with a different IP."""
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    await reg.register("RECL_IP1", conn1, "10.0.0.1", _now(), _now() + 3600)
    await reg.mark_offline("RECL_IP1")
    result = await reg.try_reclaim("RECL_IP1", conn2, "10.0.0.2")
    assert result is None
    await reg.close()


async def test_try_reclaim_expired_returns_none() -> None:
    """Cannot reclaim an expired mount (TTL passed while offline)."""
    reg = await _make_registry(":memory:")
    now = _now()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()

    # Create a mount that already expired
    await reg.register("RECL_EX1", conn1, "10.0.0.1", now - 7200, now - 3600)
    await reg.mark_offline("RECL_EX1")

    result = await reg.try_reclaim("RECL_EX1", conn2, "10.0.0.1")
    assert result is None
    await reg.close()


async def test_try_reclaim_no_expiry_returns_zero_remaining() -> None:
    """Reclaiming a mount with no expires_at returns remaining_ttl=0."""
    reg = await _make_registry(":memory:")
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    await reg.register("RECL_NE1", conn1, "10.0.0.1", _now(), None)
    await reg.mark_offline("RECL_NE1")

    result = await reg.try_reclaim("RECL_NE1", conn2, "10.0.0.1")
    assert result is not None
    assert result.remaining_ttl == 0
    await reg.close()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


async def test_close_closes_connection() -> None:
    reg = await _make_registry(":memory:")
    await reg.close()
    # Further operations should fail (aiosqlite closes the underlying sqlite3 conn)
    with pytest.raises(Exception):
        await reg.has_mount("ANYTHING")


# ---------------------------------------------------------------------------
# Config extension: db_path
# ---------------------------------------------------------------------------


def test_relay_config_has_db_path_from_yaml() -> None:
    """RelayConfig loads db_path from config.yaml."""
    from relay.app.config import load_config

    config_path = Path(__file__).resolve().parent.parent.parent / "relay" / "config.yaml"
    config = load_config(config_path)
    assert config.db_path == "/tmp/mounts.db"


def test_relay_config_db_path_env_override() -> None:
    """RELAY_DB_PATH env var overrides config.yaml."""
    import os
    from unittest.mock import patch

    from relay.app.config import load_config

    config_path = Path(__file__).resolve().parent.parent.parent / "relay" / "config.yaml"
    with patch.dict(os.environ, {"RELAY_DB_PATH": "/custom/path.db"}):
        config = load_config(config_path)
    assert config.db_path == "/custom/path.db"
