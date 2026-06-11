"""Tests for shared.sqlite_kernel — aiosqlite bootstrap helpers."""

from pathlib import Path

import pytest

from shared.sqlite_kernel import is_new_db, open_wal_db, run_schema

_DDL = ["CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"]


def test_is_new_db_memory_always_new() -> None:
    assert is_new_db(":memory:") is True


def test_is_new_db_missing_file_is_new(tmp_path: Path) -> None:
    assert is_new_db(str(tmp_path / "nope.db")) is True


def test_is_new_db_existing_file_is_not_new(tmp_path: Path) -> None:
    p = tmp_path / "exists.db"
    p.write_bytes(b"")
    assert is_new_db(str(p)) is False


def test_is_new_db_rejects_empty_path() -> None:
    with pytest.raises(ValueError):
        is_new_db("")


async def test_open_wal_db_enables_wal(tmp_path: Path) -> None:
    db = await open_wal_db(str(tmp_path / "wal.db"))
    try:
        async with db.execute("PRAGMA journal_mode") as cur:
            row = await cur.fetchone()
        assert row is not None
        assert str(row[0]).lower() == "wal"
    finally:
        await db.close()


async def test_open_wal_db_rejects_empty_path() -> None:
    with pytest.raises(ValueError):
        await open_wal_db("")


async def test_run_schema_creates_tables_and_commits(tmp_path: Path) -> None:
    path = str(tmp_path / "schema.db")
    db = await open_wal_db(path)
    try:
        await run_schema(db, _DDL)
        await db.execute("INSERT INTO t(v) VALUES ('x')")
        await db.commit()
        async with db.execute("SELECT COUNT(*) FROM t") as cur:
            row = await cur.fetchone()
        assert row is not None and row[0] == 1
    finally:
        await db.close()


async def test_run_schema_rejects_empty_statements(tmp_path: Path) -> None:
    db = await open_wal_db(":memory:")
    try:
        with pytest.raises(ValueError):
            await run_schema(db, [])
    finally:
        await db.close()
