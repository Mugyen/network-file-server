"""SQLite-backed mount registry — persists mount metadata across relay restarts.

Replaces the in-memory MountRegistry with a SQLite-backed implementation.
Live TunnelConnection objects are held in an in-memory dict (cannot be serialized).
SQLite is the source of truth for all metadata (status, TTL, IP, timestamps).
"""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

from accounts import AccessMode, Role, SubjectType
from relay.app.enums import AccessRequestStatus, MountStatus
from relay.app.exceptions import (
    AccessRequestNotFoundError,
    MountExpiredError,
    MountNotFoundError,
    MountOfflineError,
)
from shared.sqlite_kernel import is_new_db, open_wal_db, run_schema

from relay.app.services.mount_registry import (
    AccessRequest,
    MountPolicy,
    MountRecord,
    PolicyEntry,
)

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
    ttl_warned INTEGER NOT NULL DEFAULT 0,
    owner_user_id INTEGER,
    access_mode TEXT NOT NULL DEFAULT 'open',
    has_password INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_POLICY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mount_policy (
    code TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (code, subject_type, subject_id)
)
"""

_CREATE_ACCESS_REQUESTS_SQL = """
CREATE TABLE IF NOT EXISTS access_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    UNIQUE (code, user_id)
)
"""

# Columns added after the initial v1.2 schema; migrated on existing DBs.
_MIGRATION_COLUMNS: dict[str, str] = {
    "owner_user_id": "ALTER TABLE mounts ADD COLUMN owner_user_id INTEGER",
    "access_mode": "ALTER TABLE mounts ADD COLUMN access_mode TEXT NOT NULL DEFAULT 'open'",
    "has_password": "ALTER TABLE mounts ADD COLUMN has_password INTEGER NOT NULL DEFAULT 0",
}

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


def _row_to_access_request(row: tuple) -> AccessRequest:
    return AccessRequest(
        id=row[0],
        code=row[1],
        user_id=row[2],
        status=AccessRequestStatus(row[3]),
        created_at=row[4],
    )


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
        new_db = is_new_db(db_path)

        # WAL: registrations, TTL sweeps, and access-request writes run
        # concurrently — rollback-journal mode serializes them behind an
        # exclusive lock. (Matches the server's ServerStateStore.)
        db = await open_wal_db(db_path)
        await run_schema(db, [
            _CREATE_TABLE_SQL,
            _CREATE_IP_INDEX_SQL,
            _CREATE_STATUS_INDEX_SQL,
            _CREATE_POLICY_TABLE_SQL,
            _CREATE_ACCESS_REQUESTS_SQL,
        ])

        # Migrate pre-v1.3 databases: add owner/access columns if missing.
        async with db.execute("PRAGMA table_info(mounts)") as cursor:
            existing_cols = {row[1] for row in await cursor.fetchall()}
        for col, alter_sql in _MIGRATION_COLUMNS.items():
            if col not in existing_cols:
                await db.execute(alter_sql)

        await db.commit()

        if new_db:
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

        connection = self._connections[code]
        # A torn-down agent connection may linger in the map if mark_offline
        # was a race-guard no-op (status flipped by reclaim churn). Treat it
        # as offline so the proxy returns a clean mount-offline response
        # instead of RuntimeError on the next send to a closed WebSocket.
        if connection.is_closed:
            raise MountOfflineError(code)

        return connection

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

    async def mark_ttl_warned(self, code: str) -> None:
        """Persist that a TTL warning was sent for this mount.

        The TTL sweep reads mounts fresh from SQLite each iteration, so the
        warned flag must be persisted — otherwise every sweep re-warns every
        mount inside the warning window. register() resets the flag to 0, so
        a reconnecting mount earns a fresh warning for its new TTL.

        Raises:
            MountNotFoundError: If code does not exist.
        """
        cursor = await self._db.execute(
            "UPDATE mounts SET ttl_warned = 1 WHERE code = ?", (code,)
        )
        if cursor.rowcount == 0:
            raise MountNotFoundError(code)
        await self._db.commit()

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

    async def try_reclaim_as_owner(
        self,
        code: str,
        connection: "TunnelConnection",
        owner_user_id: int,
    ) -> ReclaimResult | None:
        """Reclaim an OFFLINE mount by code + owner identity (IP-independent).

        Account owners may reconnect from a different IP, so ownership —
        not the source IP — authorises the reclaim. Returns None if the
        code is unknown, not OFFLINE, owned by someone else, or expired.
        """
        async with self._db.execute(
            "SELECT status, owner_user_id, expires_at FROM mounts WHERE code = ?",
            (code,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        status, stored_owner, expires_at = row
        if status != MountStatus.OFFLINE.value:
            return None
        if stored_owner is None or stored_owner != owner_user_id:
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

    async def set_owner_policy(
        self,
        code: str,
        owner_user_id: int | None,
        access_mode: AccessMode,
        has_password: bool,
        entries: list[PolicyEntry],
    ) -> None:
        """Persist a mount's owner + access policy, replacing any prior policy.

        Raises:
            MountNotFoundError: if the mount code is not registered.
        """
        cursor = await self._db.execute(
            "UPDATE mounts SET owner_user_id = ?, access_mode = ?, has_password = ? "
            "WHERE code = ?",
            (owner_user_id, access_mode.value, 1 if has_password else 0, code),
        )
        if cursor.rowcount == 0:
            raise MountNotFoundError(code)

        await self._db.execute(
            "DELETE FROM mount_policy WHERE code = ?", (code,)
        )
        for entry in entries:
            await self._db.execute(
                "INSERT OR REPLACE INTO mount_policy "
                "(code, subject_type, subject_id, role) VALUES (?, ?, ?, ?)",
                (
                    code,
                    entry.subject_type.value,
                    entry.subject_id,
                    entry.role.value,
                ),
            )
        await self._db.commit()

    async def get_policy(self, code: str) -> MountPolicy:
        """Return the access policy for a mount.

        Raises:
            MountNotFoundError: if the mount code is not registered.
        """
        async with self._db.execute(
            "SELECT owner_user_id, access_mode, has_password FROM mounts "
            "WHERE code = ?",
            (code,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise MountNotFoundError(code)

        owner_user_id, access_mode, has_password = row
        async with self._db.execute(
            "SELECT subject_type, subject_id, role FROM mount_policy "
            "WHERE code = ?",
            (code,),
        ) as cursor:
            policy_rows = await cursor.fetchall()

        entries = tuple(
            PolicyEntry(
                subject_type=SubjectType(st),
                subject_id=sid,
                role=Role(role),
            )
            for st, sid, role in policy_rows
        )
        return MountPolicy(
            code=code,
            owner_user_id=owner_user_id,
            access_mode=AccessMode(access_mode),
            has_password=bool(has_password),
            entries=entries,
        )

    async def add_policy_entry(
        self,
        code: str,
        subject_type: SubjectType,
        subject_id: int,
        role: Role,
    ) -> None:
        """Add/replace a single allowlist entry (does not touch owner/mode).

        Raises:
            MountNotFoundError: if the mount code is not registered.
        """
        async with self._db.execute(
            "SELECT 1 FROM mounts WHERE code = ?", (code,)
        ) as cursor:
            if await cursor.fetchone() is None:
                raise MountNotFoundError(code)
        await self._db.execute(
            "INSERT OR REPLACE INTO mount_policy "
            "(code, subject_type, subject_id, role) VALUES (?, ?, ?, ?)",
            (code, subject_type.value, subject_id, role.value),
        )
        await self._db.commit()

    async def create_access_request(
        self, code: str, user_id: int
    ) -> AccessRequest:
        """Create a pending access request, or return the existing one.

        Deduped on (code, user_id) so a user cannot spam duplicate
        pending requests.
        """
        now = time.time()
        await self._db.execute(
            "INSERT OR IGNORE INTO access_requests "
            "(code, user_id, status, created_at) VALUES (?, ?, ?, ?)",
            (code, user_id, AccessRequestStatus.PENDING.value, now),
        )
        await self._db.commit()
        async with self._db.execute(
            "SELECT id, code, user_id, status, created_at "
            "FROM access_requests WHERE code = ? AND user_id = ?",
            (code, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        return _row_to_access_request(row)

    async def get_access_request(self, request_id: int) -> AccessRequest:
        """Return an access request. Raises AccessRequestNotFoundError."""
        async with self._db.execute(
            "SELECT id, code, user_id, status, created_at "
            "FROM access_requests WHERE id = ?",
            (request_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise AccessRequestNotFoundError(request_id)
        return _row_to_access_request(row)

    async def list_all_access_requests(self) -> list[AccessRequest]:
        async with self._db.execute(
            "SELECT id, code, user_id, status, created_at "
            "FROM access_requests ORDER BY id DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_access_request(r) for r in rows]

    async def list_access_requests_for_user(
        self, user_id: int
    ) -> list[AccessRequest]:
        async with self._db.execute(
            "SELECT id, code, user_id, status, created_at "
            "FROM access_requests WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_access_request(r) for r in rows]

    async def list_access_requests_for_owner(
        self, owner_user_id: int
    ) -> list[AccessRequest]:
        """Requests targeting mounts owned by ``owner_user_id``."""
        async with self._db.execute(
            "SELECT r.id, r.code, r.user_id, r.status, r.created_at "
            "FROM access_requests r JOIN mounts m ON m.code = r.code "
            "WHERE m.owner_user_id = ? ORDER BY r.id DESC",
            (owner_user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_access_request(r) for r in rows]

    async def resolve_access_request(
        self, request_id: int, status: AccessRequestStatus
    ) -> None:
        """Set an access request's terminal status.

        Raises AccessRequestNotFoundError if the id is unknown.
        """
        cursor = await self._db.execute(
            "UPDATE access_requests SET status = ? WHERE id = ?",
            (status.value, request_id),
        )
        if cursor.rowcount == 0:
            raise AccessRequestNotFoundError(request_id)
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
