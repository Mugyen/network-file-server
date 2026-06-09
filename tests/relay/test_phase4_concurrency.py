"""Phase-4 concurrency fixes: WAL journal mode, dedicated FileTtlDb
connection, and event-loop liveness while a slow directory listing runs."""

import asyncio
import time
from pathlib import Path

import aiosqlite

from accounts import SqliteAccountStore
from relay.app.services.file_ttl_db import FileTtlDb
from relay.app.services.sqlite_registry import SqliteMountRegistry


async def _journal_mode(db: aiosqlite.Connection) -> str:
    async with db.execute("PRAGMA journal_mode") as cursor:
        row = await cursor.fetchone()
    return row[0]


async def test_registry_uses_wal(tmp_path: Path) -> None:
    registry = await SqliteMountRegistry.create(str(tmp_path / "mounts.db"))
    assert (await _journal_mode(registry._db)) == "wal"
    await registry.close()


async def test_account_store_uses_wal(tmp_path: Path) -> None:
    store = await SqliteAccountStore.create(str(tmp_path / "accounts.db"))
    assert (await _journal_mode(store._db)) == "wal"
    await store.close()


async def test_file_ttl_db_has_own_connection(tmp_path: Path) -> None:
    """FileTtlDb.create opens a dedicated WAL connection on the same DB file
    and operates independently of the registry connection."""
    db_path = str(tmp_path / "mounts.db")
    registry = await SqliteMountRegistry.create(db_path)
    ttl_db = await FileTtlDb.create(db_path)

    assert ttl_db._db is not registry._db
    assert (await _journal_mode(ttl_db._db)) == "wal"

    await ttl_db.record_file_ttl("code1", "a.txt", ttl_seconds=3600)
    records = await ttl_db.get_ttl_for_mount("code1")
    assert [r[0] for r in records] == ["a.txt"]

    await ttl_db.close()
    await registry.close()


async def test_slow_listing_does_not_block_event_loop(tmp_path: Path, monkeypatch) -> None:
    """A slow (blocking) directory listing must not stall concurrent requests:
    list_directory is offloaded to a thread via asyncio.to_thread."""
    import httpx

    from server.app.config import create_default_config
    from server.app.main import create_app
    from server.app.routers import files as files_router
    from server.app.models.schemas import DirectoryListing

    app = create_app(create_default_config(shared_folder=tmp_path, port=8000))

    def slow_list(base_dir, relative_path):
        time.sleep(0.5)  # deliberately blocking — must run off the loop
        return DirectoryListing(path=relative_path, entries=[])

    monkeypatch.setattr(files_router, "list_directory", slow_list)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start = time.monotonic()

        async def fast_probe() -> float:
            # Give the slow request a head start so it is mid-listing.
            await asyncio.sleep(0.05)
            response = await client.get("/api/server-info")
            assert response.status_code == 200
            return time.monotonic() - start

        slow_task = asyncio.create_task(client.get("/api/files?path="))
        probe_elapsed = await fast_probe()
        slow_response = await slow_task

    assert slow_response.status_code == 200
    # If the loop were blocked, the probe couldn't finish before ~0.5s.
    assert probe_elapsed < 0.4, (
        f"event loop appears blocked: probe took {probe_elapsed:.3f}s"
    )
