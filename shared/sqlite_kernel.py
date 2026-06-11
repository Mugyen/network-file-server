"""Shared aiosqlite connection bootstrap.

All async SQLite stores in this repo (relay mount registry, relay file-TTL
db, accounts store) open their database the same way: validate the path,
connect, enable WAL, run schema DDL, commit. This module is that one way.

Synchronous stores (server's ServerStateStore) have a different threading
contract and deliberately do not use this kernel.
"""

from collections.abc import Sequence
from pathlib import Path

import aiosqlite


def is_new_db(db_path: str) -> bool:
    """True if ``db_path`` refers to a database that does not exist yet.

    ``:memory:`` databases are always new.

    Raises:
        ValueError: If db_path is not a non-empty string.
    """
    if not isinstance(db_path, str) or len(db_path) == 0:
        raise ValueError("db_path must be a non-empty string")
    return db_path == ":memory:" or not Path(db_path).exists()


async def open_wal_db(db_path: str) -> aiosqlite.Connection:
    """Open an aiosqlite connection with WAL journaling enabled.

    WAL allows concurrent readers during writes — every async store in
    this repo wants that.

    Raises:
        ValueError: If db_path is not a non-empty string.
    """
    if not isinstance(db_path, str) or len(db_path) == 0:
        raise ValueError("db_path must be a non-empty string")
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def run_schema(db: aiosqlite.Connection, statements: Sequence[str]) -> None:
    """Execute schema DDL statements and commit.

    Raises:
        ValueError: If statements is empty.
    """
    if len(statements) == 0:
        raise ValueError("statements must be a non-empty sequence")
    for stmt in statements:
        await db.execute(stmt)
    await db.commit()
