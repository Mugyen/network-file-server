"""SQLite-backed mount registry — persists mount metadata across relay restarts.

Replaces the in-memory MountRegistry with a SQLite-backed implementation.
Live TunnelConnection objects are held in an in-memory dict (cannot be serialized).
SQLite is the source of truth for all metadata (status, TTL, IP, timestamps).
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from relay.app.enums import MountStatus
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError
from relay.app.services.mount_registry import MountRecord

if TYPE_CHECKING:
    from tunnel.connection import TunnelConnection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mounts (
    code TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'online',
    agent_ip TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL,
    ttl_warned INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_IP_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mounts_agent_ip ON mounts (agent_ip)
"""

_CREATE_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mounts_status ON mounts (status)
"""

# Retention window: expired records kept for 6 hours before permanent deletion
_RETENTION_SECONDS = 6 * 3600


@dataclass(frozen=True)
class ReclaimResult:
    """Result of a successful mount reclaim."""

    remaining_ttl: int


class SqliteMountRegistry:
    """SQLite-backed mount registry with in-memory connection tracking.

    SQLite stores: code, status, agent_ip, created_at, expires_at, ttl_warned.
    In-memory dict stores: code -> TunnelConnection (cannot be serialized).

    Use the async factory ``create()`` to instantiate — the constructor is not
    meant to be called directly.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db: aiosqlite.Connection = db
        self._connections: dict[str, "TunnelConnection"] = {}

    @classmethod
    async def create(cls, db_path: str) -> "SqliteMountRegistry":
        """Create and initialise a SQLite-backed registry.

        Opens the database, creates the schema if needed, runs startup
        cleanup, and returns a ready-to-use registry.
        """
        is_new_db = db_path == ":memory:" or not Path(db_path).exists()

        db = await aiosqlite.connect(db_path)
        await db.execute("PRAGMA journal_mode=DELETE")
        await db.execute(_CREATE_TABLE_SQL)
        await db.execute(_CREATE_IP_INDEX_SQL)
        await db.execute(_CREATE_STATUS_INDEX_SQL)
        await db.commit()

        if is_new_db:
            logger.info("No existing mount database -- starting fresh")

        registry = cls(db)
        await registry._startup_cleanup()
        return registry

    # ------------------------------------------------------------------
    # Public API — async equivalents of MountRegistry methods
    # ------------------------------------------------------------------

    async def register(
        self,
        code: str,
        connection: "TunnelConnection | None",
        agent_ip: str,
        created_at: float,
        expires_at: float | None,
    ) -> None:
        """Register a mount. Overwrites if code already exists (INSERT OR REPLACE).

        Pass connection=None for local mounts (e.g. drop box) that don't use
        a tunnel. get_connection() will raise RuntimeError for these mounts.

        Raises:
            ValueError: If code is empty.
        """
        if not code:
            raise ValueError("Mount code must not be empty")

        await self._db.execute(
            "INSERT OR REPLACE INTO mounts (code, status, agent_ip, created_at, expires_at, ttl_warned) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (code, MountStatus.ONLINE.value, agent_ip, created_at, expires_at),
        )
        await self._db.commit()
        if connection is not None:
            self._connections[code] = connection

    async def deregister(self, code: str) -> None:
        """Remove the mount record entirely from SQLite and memory.

        Raises:
            MountNotFoundError: If code is not present.
        """
        cursor = await self._db.execute(
            "DELETE FROM mounts WHERE code = ?", (code,)
        )
        if cursor.rowcount == 0:
            raise MountNotFoundError(code)
        await self._db.commit()
        self._connections.pop(code, None)

    async def get_connection(self, code: str) -> "TunnelConnection":
        """Return the live TunnelConnection for a mount code.

        Raises:
            MountNotFoundError: code is not registered.
            MountOfflineError: mount is registered but OFFLINE.
            MountExpiredError: mount is registered but EXPIRED.
        """
        async with self._db.execute(
            "SELECT status FROM mounts WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            raise MountNotFoundError(code)

        status = row[0]
        if status == MountStatus.OFFLINE.value:
            raise MountOfflineError(code)
        if status == MountStatus.EXPIRED.value:
            raise MountExpiredError(code)

        if code not in self._connections:
            raise RuntimeError(f"Mount '{code}' has no tunnel connection (local mount)")

        return self._connections[code]

    async def mark_offline(self, code: str) -> None:
        """Transition an ONLINE mount to OFFLINE. No-op for non-ONLINE mounts.

        Race guard: if the mount is already OFFLINE or EXPIRED (e.g. reclaimed
        by a new connection), this is a safe no-op. Only ONLINE -> OFFLINE
        transitions are performed.

        Raises:
            MountNotFoundError: If code does not exist.
        """
        async with self._db.execute(
            "SELECT status FROM mounts WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            raise MountNotFoundError(code)

        if row[0] == MountStatus.ONLINE.value:
            await self._db.execute(
                "UPDATE mounts SET status = ? WHERE code = ?",
                (MountStatus.OFFLINE.value, code),
            )
            await self._db.commit()
            self._connections.pop(code, None)

    async def expire(self, code: str) -> None:
        """Transition a mount to EXPIRED status, retaining the SQLite record.

        Used by the TTL sweep for the online/offline -> expired transition.
        The record is kept for the 6h retention window before permanent deletion.

        Raises:
            MountNotFoundError: If code does not exist.
        """
        async with self._db.execute(
            "SELECT 1 FROM mounts WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            raise MountNotFoundError(code)

        await self._db.execute(
            "UPDATE mounts SET status = ? WHERE code = ?",
            (MountStatus.EXPIRED.value, code),
        )
        await self._db.commit()
        self._connections.pop(code, None)

    async def has_mount(self, code: str) -> bool:
        """Return True if a record exists for the given code, regardless of status."""
        async with self._db.execute(
            "SELECT 1 FROM mounts WHERE code = ?", (code,)
        ) as cursor:
            row = await cursor.fetchone()
        return row is not None

    async def count_mounts_by_ip(self, agent_ip: str) -> int:
        """Count active (non-expired) mounts registered by this IP."""
        async with self._db.execute(
            "SELECT COUNT(*) FROM mounts WHERE agent_ip = ? AND status != ?",
            (agent_ip, MountStatus.EXPIRED.value),
        ) as cursor:
            row = await cursor.fetchone()
        return row[0]

    async def mount_count(self) -> int:
        """Return the total number of mount records in the database, regardless of status."""
        async with self._db.execute("SELECT COUNT(*) FROM mounts") as cursor:
            row = await cursor.fetchone()
        return row[0]

    async def active_mounts(self) -> list[MountRecord]:
        """Return a snapshot of all non-EXPIRED mount records.

        The connection field is populated from the in-memory dict for ONLINE
        mounts and is None for OFFLINE mounts (loaded from disk).
        """
        async with self._db.execute(
            "SELECT code, status, agent_ip, created_at, expires_at, ttl_warned "
            "FROM mounts WHERE status != ?",
            (MountStatus.EXPIRED.value,),
        ) as cursor:
            rows = await cursor.fetchall()

        result: list[MountRecord] = []
        for code, status, agent_ip, created_at, expires_at, ttl_warned in rows:
            result.append(
                MountRecord(
                    code=code,
                    connection=self._connections.get(code),  # type: ignore[arg-type]
                    status=MountStatus(status),
                    agent_ip=agent_ip,
                    created_at=created_at,
                    expires_at=expires_at,
                    ttl_warned=bool(ttl_warned),
                )
            )
        return result

    async def try_reclaim(
        self,
        code: str,
        connection: "TunnelConnection",
        agent_ip: str,
    ) -> ReclaimResult | None:
        """Attempt to reclaim an OFFLINE mount by code and IP match.

        Returns ReclaimResult with remaining_ttl on success, None on failure
        (code not found, not OFFLINE, IP mismatch, or expired).
        """
        async with self._db.execute(
            "SELECT status, agent_ip, expires_at FROM mounts WHERE code = ?",
            (code,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        status, stored_ip, expires_at = row

        if status != MountStatus.OFFLINE.value:
            return None
        if stored_ip != agent_ip:
            return None

        now = time.time()
        if expires_at is not None and expires_at <= now:
            return None

        await self._db.execute(
            "UPDATE mounts SET status = ? WHERE code = ?",
            (MountStatus.ONLINE.value, code),
        )
        await self._db.commit()
        self._connections[code] = connection

        remaining = int(expires_at - now) if expires_at is not None else 0
        return ReclaimResult(remaining_ttl=remaining)

    async def delete_expired_before(self, cutoff: float) -> None:
        """Delete EXPIRED records whose expires_at is before the cutoff.

        Used by the TTL sweep for retention cleanup.
        """
        await self._db.execute(
            "DELETE FROM mounts WHERE status = ? AND expires_at IS NOT NULL AND expires_at < ?",
            (MountStatus.EXPIRED.value, cutoff),
        )
        await self._db.commit()

    async def close(self) -> None:
        """Close the aiosqlite connection."""
        await self._db.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _startup_cleanup(self) -> None:
        """Run cold-start cleanup: delete stale expired, mark newly-expired, set ONLINE to OFFLINE."""
        now = time.time()

        # 1. Delete records that expired more than 6h ago (past retention window)
        retention_cutoff = now - _RETENTION_SECONDS
        cursor = await self._db.execute(
            "DELETE FROM mounts WHERE status = ? AND expires_at IS NOT NULL AND expires_at < ?",
            (MountStatus.EXPIRED.value, retention_cutoff),
        )
        deleted_count = cursor.rowcount

        # 2. Mark any mounts whose expires_at has passed as EXPIRED (within retention window)
        cursor = await self._db.execute(
            "UPDATE mounts SET status = ? WHERE expires_at IS NOT NULL AND expires_at < ?",
            (MountStatus.EXPIRED.value, now),
        )
        newly_expired_count = cursor.rowcount

        # 3. Mark all remaining ONLINE mounts as OFFLINE
        cursor = await self._db.execute(
            "UPDATE mounts SET status = ? WHERE status = ?",
            (MountStatus.OFFLINE.value, MountStatus.ONLINE.value),
        )
        marked_offline_count = cursor.rowcount

        await self._db.commit()

        if deleted_count or newly_expired_count or marked_offline_count:
            logger.info(
                "Startup cleanup: deleted %d expired records, "
                "marked %d newly expired, marked %d as offline",
                deleted_count,
                newly_expired_count,
                marked_offline_count,
            )
