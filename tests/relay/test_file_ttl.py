"""Tests for file TTL database, sweep, and boot-time cleanup."""

import os
import time
from pathlib import Path

import aiosqlite
import pytest

from relay.app.services.file_ttl_db import FileTtlDb
from relay.app.services.file_ttl_sweep import file_ttl_sweep_once


@pytest.fixture
async def file_ttl_db():
    """Create an in-memory FileTtlDb for testing."""
    db = await aiosqlite.connect(":memory:")
    ttl_db = FileTtlDb(db)
    await ttl_db.init_table()
    yield ttl_db
    await db.close()


# ---------------------------------------------------------------------------
# FileTtlDb CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_and_get_expired(file_ttl_db: FileTtlDb) -> None:
    """record_file_ttl stores a record, get_expired returns it after expiry."""
    # Record with TTL of -1 second (already expired)
    await file_ttl_db.record_file_ttl("mount1", "test.txt", -1)
    expired = await file_ttl_db.get_expired()
    assert len(expired) == 1
    assert expired[0][0] == "mount1"
    assert expired[0][1] == "test.txt"


@pytest.mark.asyncio
async def test_record_not_expired_yet(file_ttl_db: FileTtlDb) -> None:
    """Record with future TTL does not appear in get_expired."""
    await file_ttl_db.record_file_ttl("mount1", "test.txt", 3600)
    expired = await file_ttl_db.get_expired()
    assert len(expired) == 0


@pytest.mark.asyncio
async def test_delete_record(file_ttl_db: FileTtlDb) -> None:
    """delete_record removes a specific record."""
    await file_ttl_db.record_file_ttl("mount1", "a.txt", -1)
    await file_ttl_db.record_file_ttl("mount1", "b.txt", -1)
    await file_ttl_db.delete_record("mount1", "a.txt")
    expired = await file_ttl_db.get_expired()
    assert len(expired) == 1
    assert expired[0][1] == "b.txt"


@pytest.mark.asyncio
async def test_get_ttl_for_mount(file_ttl_db: FileTtlDb) -> None:
    """get_ttl_for_mount returns all records for a mount."""
    await file_ttl_db.record_file_ttl("mount1", "a.txt", 3600)
    await file_ttl_db.record_file_ttl("mount2", "b.txt", 3600)
    records = await file_ttl_db.get_ttl_for_mount("mount1")
    assert len(records) == 1
    assert records[0][0] == "a.txt"


@pytest.mark.asyncio
async def test_delete_expired_for_mount(file_ttl_db: FileTtlDb) -> None:
    """delete_expired_for_mount returns and removes expired paths."""
    await file_ttl_db.record_file_ttl("mount1", "old.txt", -1)
    await file_ttl_db.record_file_ttl("mount1", "new.txt", 3600)
    paths = await file_ttl_db.delete_expired_for_mount("mount1")
    assert paths == ["old.txt"]
    # Only the non-expired record remains
    records = await file_ttl_db.get_ttl_for_mount("mount1")
    assert len(records) == 1
    assert records[0][0] == "new.txt"


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sweep_deletes_expired_file(file_ttl_db: FileTtlDb, tmp_path: Path) -> None:
    """Sweep deletes expired files from filesystem and records from SQLite."""
    # Create a physical file in the dropbox directory
    dropbox_dir = tmp_path / "dropbox"
    dropbox_dir.mkdir()
    test_file = dropbox_dir / "expired.txt"
    test_file.write_text("expired content")

    await file_ttl_db.record_file_ttl("dropbox", "expired.txt", -1)

    deleted = await file_ttl_sweep_once(file_ttl_db, tmp_path, "dropbox", None)

    assert deleted == ["expired.txt"]
    assert not test_file.exists()
    # Record should be gone
    expired = await file_ttl_db.get_expired()
    assert len(expired) == 0


@pytest.mark.asyncio
async def test_sweep_broadcasts_toast(file_ttl_db: FileTtlDb, tmp_path: Path) -> None:
    """Sweep broadcasts a toast message for each deleted file."""
    dropbox_dir = tmp_path / "dropbox"
    dropbox_dir.mkdir()
    (dropbox_dir / "gone.txt").write_text("bye")

    await file_ttl_db.record_file_ttl("dropbox", "gone.txt", -1)

    toasts: list[dict] = []

    async def mock_broadcast(msg: dict) -> None:
        toasts.append(msg)

    await file_ttl_sweep_once(file_ttl_db, tmp_path, "dropbox", mock_broadcast)

    assert len(toasts) == 1
    assert "gone.txt" in toasts[0]["message"]
    assert toasts[0]["type"] == "toast"
    assert toasts[0]["toast_type"] == "file_expired"
    assert toasts[0]["device_name"] == "System"
    assert "timestamp" in toasts[0]


@pytest.mark.asyncio
async def test_sweep_skips_agent_mount_files(file_ttl_db: FileTtlDb, tmp_path: Path) -> None:
    """Sweep removes records for agent mounts but does NOT delete files (no filesystem access)."""
    await file_ttl_db.record_file_ttl("agent-mount", "remote.txt", -1)

    deleted = await file_ttl_sweep_once(file_ttl_db, tmp_path, "dropbox", None)

    # No files deleted (agent mount, no filesystem access)
    assert deleted == []
    # But the record is still removed
    expired = await file_ttl_db.get_expired()
    assert len(expired) == 0
