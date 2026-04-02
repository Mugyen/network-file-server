"""File TTL database operations -- tracks per-file expiry metadata in SQLite.

Uses the same aiosqlite connection as the mount registry to avoid
multiple database handles. Records are created on upload and deleted
by the background sweep when files expire.
"""

import time

import aiosqlite

_CREATE_FILE_TTL_TABLE = """
CREATE TABLE IF NOT EXISTS file_ttl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mount_code TEXT NOT NULL,
    file_path TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(mount_code, file_path)
)
"""

_CREATE_FILE_TTL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_file_ttl_expires ON file_ttl (expires_at)
"""


class FileTtlDb:
    """CRUD operations for the file_ttl SQLite table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def init_table(self) -> None:
        """Create the file_ttl table and index if they don't exist."""
        await self._db.execute(_CREATE_FILE_TTL_TABLE)
        await self._db.execute(_CREATE_FILE_TTL_INDEX)
        await self._db.commit()

    async def record_file_ttl(self, mount_code: str, file_path: str, ttl_seconds: int) -> None:
        """Record a file TTL. Overwrites if the same file already has a TTL record."""
        now = time.time()
        expires_at = now + ttl_seconds
        await self._db.execute(
            "INSERT OR REPLACE INTO file_ttl (mount_code, file_path, expires_at, created_at) "
            "VALUES (?, ?, ?, ?)",
            (mount_code, file_path, expires_at, now),
        )
        await self._db.commit()

    async def get_expired(self) -> list[tuple[str, str, float]]:
        """Return (mount_code, file_path, expires_at) for all expired records."""
        now = time.time()
        async with self._db.execute(
            "SELECT mount_code, file_path, expires_at FROM file_ttl WHERE expires_at <= ?",
            (now,),
        ) as cursor:
            return await cursor.fetchall()

    async def get_expired_for_mount(self, mount_code: str) -> list[tuple[str, float]]:
        """Return (file_path, expires_at) for expired records in a specific mount."""
        now = time.time()
        async with self._db.execute(
            "SELECT file_path, expires_at FROM file_ttl WHERE mount_code = ? AND expires_at <= ?",
            (mount_code, now),
        ) as cursor:
            return await cursor.fetchall()

    async def delete_record(self, mount_code: str, file_path: str) -> None:
        """Delete a single file TTL record."""
        await self._db.execute(
            "DELETE FROM file_ttl WHERE mount_code = ? AND file_path = ?",
            (mount_code, file_path),
        )
        await self._db.commit()

    async def get_ttl_for_mount(self, mount_code: str) -> list[tuple[str, float]]:
        """Return (file_path, expires_at) for all files in a mount with TTL."""
        async with self._db.execute(
            "SELECT file_path, expires_at FROM file_ttl WHERE mount_code = ?",
            (mount_code,),
        ) as cursor:
            return await cursor.fetchall()

    async def delete_expired_for_mount(self, mount_code: str) -> list[str]:
        """Delete expired records for a mount. Returns list of deleted file paths."""
        now = time.time()
        async with self._db.execute(
            "SELECT file_path FROM file_ttl WHERE mount_code = ? AND expires_at <= ?",
            (mount_code, now),
        ) as cursor:
            rows = await cursor.fetchall()
        paths = [row[0] for row in rows]
        if paths:
            await self._db.execute(
                "DELETE FROM file_ttl WHERE mount_code = ? AND expires_at <= ?",
                (mount_code, now),
            )
            await self._db.commit()
        return paths


_file_ttl_db: FileTtlDb | None = None


def get_file_ttl_db() -> FileTtlDb:
    """Return the global FileTtlDb singleton.

    Raises:
        RuntimeError: If set_file_ttl_db() has not been called.
    """
    if _file_ttl_db is None:
        raise RuntimeError("FileTtlDb not initialized. Call set_file_ttl_db() first.")
    return _file_ttl_db


def set_file_ttl_db(db: FileTtlDb | None) -> None:
    """Install the global FileTtlDb singleton."""
    global _file_ttl_db
    _file_ttl_db = db
