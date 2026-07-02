"""SQLite-backed :class:`AccountStore` implementation.

Mirrors the lifecycle conventions of the relay's ``SqliteMountRegistry``
(async ``create()`` factory, ``PRAGMA journal_mode=WAL``,
``CREATE TABLE IF NOT EXISTS``, explicit ``close()``).
"""

import logging
import secrets
import time
from pathlib import Path
from typing import Any

import aiosqlite

from accounts.enums import SubjectType
from accounts.passwords import hash_password
from accounts.exceptions import (
    DuplicateMembershipError,
    GroupCycleError,
    GroupNameTakenError,
    GroupNotFoundError,
    MembershipNotFoundError,
    QuotaNotSetError,
    UsernameTakenError,
    UserNotFoundError,
)
from accounts.models import Group, Membership, User
from accounts.resolve import resolve_user_groups
from accounts.store import AccountStore

logger = logging.getLogger(__name__)


def _inserted_rowid(cursor: aiosqlite.Cursor) -> int:
    """Return the rowid of a just-executed INSERT.

    sqlite3 types lastrowid as Optional because it is None before any INSERT;
    after a successful INSERT it is always set, so None here means a broken
    invariant worth failing loudly on.
    """
    rowid = cursor.lastrowid
    if rowid is None:
        raise RuntimeError("INSERT produced no rowid — sqlite invariant violated")
    return rowid

_CREATE_USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash BLOB NOT NULL,
    created_at REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
)
"""

_CREATE_GROUPS_SQL = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
)
"""

_CREATE_MEMBERSHIPS_SQL = """
CREATE TABLE IF NOT EXISTS memberships (
    group_id INTEGER NOT NULL,
    member_type TEXT NOT NULL,
    member_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, member_type, member_id)
)
"""

_CREATE_USER_QUOTA_SQL = """
CREATE TABLE IF NOT EXISTS user_quota (
    user_id INTEGER PRIMARY KEY,
    quota_bytes INTEGER NOT NULL
)
"""

# SSO / federated login: maps an identity provider's opaque subject id
# (OIDC ``sub``, never email) to a local account. (provider, subject) is the
# stable key an app must key on — see the switchboard identity contract.
_CREATE_EXTERNAL_IDENTITIES_SQL = """
CREATE TABLE IF NOT EXISTS external_identities (
    provider TEXT NOT NULL,
    subject TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (provider, subject)
)
"""

_CREATE_EXTERNAL_USER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_external_identities_user
ON external_identities (user_id)
"""

_CREATE_MEMBER_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memberships_member
ON memberships (member_type, member_id)
"""

_CREATE_GROUP_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_memberships_group
ON memberships (group_id)
"""


class SqliteAccountStore(AccountStore):
    """SQLite implementation of the account persistence contract."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db: aiosqlite.Connection = db

    @classmethod
    async def create(cls, db_path: str) -> "SqliteAccountStore":
        """Open the database, create the schema if needed, and return a store."""
        if not isinstance(db_path, str) or len(db_path) == 0:
            raise ValueError("db_path must be a non-empty string")

        # accounts/ is a leaf package (liftable into other projects) and
        # must not import shared.sqlite_kernel — it keeps its own bootstrap.
        is_new_db = db_path == ":memory:" or not Path(db_path).exists()

        db = await aiosqlite.connect(db_path)
        # WAL allows concurrent readers during writes (signup/login bursts).
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(_CREATE_USERS_SQL)
        await db.execute(_CREATE_GROUPS_SQL)
        await db.execute(_CREATE_MEMBERSHIPS_SQL)
        await db.execute(_CREATE_USER_QUOTA_SQL)
        await db.execute(_CREATE_EXTERNAL_IDENTITIES_SQL)
        await db.execute(_CREATE_MEMBER_INDEX_SQL)
        await db.execute(_CREATE_GROUP_INDEX_SQL)
        await db.execute(_CREATE_EXTERNAL_USER_INDEX_SQL)
        await db.commit()

        if is_new_db:
            logger.info("No existing accounts database -- starting fresh")

        return cls(db)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def create_user(
        self, username: str, password_hash: bytes, email: str | None
    ) -> User:
        if not isinstance(username, str) or len(username.strip()) == 0:
            raise ValueError("username must be a non-empty string")
        if not isinstance(password_hash, (bytes, bytearray)) or len(password_hash) == 0:
            raise ValueError("password_hash must be non-empty bytes")

        normalized = username.strip()
        if await self._username_exists(normalized):
            raise UsernameTakenError(normalized)

        created_at = time.time()
        try:
            cursor = await self._db.execute(
                "INSERT INTO users (username, email, password_hash, created_at, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (normalized, email, bytes(password_hash), created_at),
            )
        except aiosqlite.IntegrityError as exc:
            # Backstop for a race between the existence check and insert.
            # Convert the storage error into the domain exception.
            raise UsernameTakenError(normalized) from exc
        await self._db.commit()

        return User(
            id=_inserted_rowid(cursor),
            username=normalized,
            email=email,
            password_hash=bytes(password_hash),
            created_at=created_at,
            is_active=True,
        )

    async def get_user_by_username(self, username: str) -> User:
        async with self._db.execute(
            "SELECT id, username, email, password_hash, created_at, is_active "
            "FROM users WHERE username = ?",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise UserNotFoundError(username)
        return self._row_to_user(row)

    async def get_user_by_id(self, user_id: int) -> User:
        async with self._db.execute(
            "SELECT id, username, email, password_hash, created_at, is_active "
            "FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise UserNotFoundError(user_id)
        return self._row_to_user(row)

    async def get_users_by_ids(self, user_ids: list[int]) -> dict[int, User]:
        if not isinstance(user_ids, list) or not all(
            isinstance(uid, int) for uid in user_ids
        ):
            raise ValueError("user_ids must be a list of ints")
        unique_ids = sorted(set(user_ids))
        if len(unique_ids) == 0:
            return {}
        placeholders = ",".join("?" * len(unique_ids))
        async with self._db.execute(
            "SELECT id, username, email, password_hash, created_at, is_active "
            f"FROM users WHERE id IN ({placeholders})",
            unique_ids,
        ) as cursor:
            rows = await cursor.fetchall()
        users = [self._row_to_user(row) for row in rows]
        return {user.id: user for user in users}

    async def set_user_active(self, user_id: int, is_active: bool) -> None:
        cursor = await self._db.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, user_id),
        )
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)
        await self._db.commit()

    async def list_users(self) -> list[User]:
        async with self._db.execute(
            "SELECT id, username, email, password_hash, created_at, is_active "
            "FROM users ORDER BY id ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_user(row) for row in rows]

    # ------------------------------------------------------------------
    # External identities (SSO / federated login)
    # ------------------------------------------------------------------

    async def get_user_by_external_id(self, provider: str, subject: str) -> User:
        async with self._db.execute(
            "SELECT u.id, u.username, u.email, u.password_hash, u.created_at, u.is_active "
            "FROM users u JOIN external_identities e ON e.user_id = u.id "
            "WHERE e.provider = ? AND e.subject = ?",
            (provider, subject),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise UserNotFoundError(f"{provider}:{subject}")
        return self._row_to_user(row)

    async def create_external_user(
        self, provider: str, subject: str, username: str, email: str | None
    ) -> User:
        if not isinstance(username, str) or len(username.strip()) == 0:
            raise ValueError("username must be a non-empty string")
        if not provider or not subject:
            raise ValueError("provider and subject must be non-empty")

        normalized = username.strip()
        if await self._username_exists(normalized):
            raise UsernameTakenError(normalized)

        # SSO-only account: store a bcrypt hash of a random, unguessable secret
        # so the NOT NULL column is satisfied and password login can never
        # succeed (verify_password returns False, no exception) for this user.
        sentinel = hash_password(secrets.token_urlsafe(32))
        created_at = time.time()
        try:
            cursor = await self._db.execute(
                "INSERT INTO users (username, email, password_hash, created_at, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (normalized, email, bytes(sentinel), created_at),
            )
            user_id = _inserted_rowid(cursor)
            await self._db.execute(
                "INSERT INTO external_identities (provider, subject, user_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (provider, subject, user_id, created_at),
            )
        except aiosqlite.IntegrityError as exc:
            await self._db.rollback()
            # Username race, or (provider, subject) already linked concurrently.
            raise UsernameTakenError(normalized) from exc
        await self._db.commit()

        return User(
            id=user_id,
            username=normalized,
            email=email,
            password_hash=bytes(sentinel),
            created_at=created_at,
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    async def create_group(self, name: str) -> Group:
        if not isinstance(name, str) or len(name.strip()) == 0:
            raise ValueError("group name must be a non-empty string")

        normalized = name.strip()
        if await self._group_name_exists(normalized):
            raise GroupNameTakenError(normalized)

        created_at = time.time()
        try:
            cursor = await self._db.execute(
                "INSERT INTO groups (name, created_at) VALUES (?, ?)",
                (normalized, created_at),
            )
        except aiosqlite.IntegrityError as exc:
            # Convert the storage uniqueness error into the domain exception.
            raise GroupNameTakenError(normalized) from exc
        await self._db.commit()
        return Group(id=_inserted_rowid(cursor), name=normalized, created_at=created_at)

    async def get_group_by_id(self, group_id: int) -> Group:
        async with self._db.execute(
            "SELECT id, name, created_at FROM groups WHERE id = ?",
            (group_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise GroupNotFoundError(group_id)
        return Group(id=row[0], name=row[1], created_at=row[2])

    async def get_group_by_name(self, name: str) -> Group:
        async with self._db.execute(
            "SELECT id, name, created_at FROM groups WHERE name = ?",
            (name,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise GroupNotFoundError(name)
        return Group(id=row[0], name=row[1], created_at=row[2])

    async def list_groups(self) -> list[Group]:
        async with self._db.execute(
            "SELECT id, name, created_at FROM groups ORDER BY id ASC"
        ) as cursor:
            rows = await cursor.fetchall()
        return [Group(id=r[0], name=r[1], created_at=r[2]) for r in rows]

    async def delete_group(self, group_id: int) -> None:
        cursor = await self._db.execute(
            "DELETE FROM groups WHERE id = ?", (group_id,)
        )
        if cursor.rowcount == 0:
            raise GroupNotFoundError(group_id)
        # Remove edges pointing to OR from this group so no dangling members remain.
        await self._db.execute(
            "DELETE FROM memberships WHERE group_id = ?", (group_id,)
        )
        await self._db.execute(
            "DELETE FROM memberships WHERE member_type = ? AND member_id = ?",
            (SubjectType.GROUP.value, group_id),
        )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Memberships
    # ------------------------------------------------------------------

    async def add_member(
        self, group_id: int, member_type: SubjectType, member_id: int
    ) -> None:
        if not isinstance(member_type, SubjectType):
            raise TypeError("member_type must be a SubjectType")

        # Validate both endpoints exist (raises GroupNotFoundError/UserNotFoundError).
        await self.get_group_by_id(group_id)
        if member_type is SubjectType.USER:
            await self.get_user_by_id(member_id)
        else:
            await self.get_group_by_id(member_id)
            if member_id == group_id:
                raise GroupCycleError(group_id, member_id)
            # New edge: group_id contains member_id. A cycle exists if
            # member_id can already reach group_id (member_id ->* group_id).
            if group_id in await self._group_descendants(member_id):
                raise GroupCycleError(group_id, member_id)

        if await self._membership_exists(group_id, member_type, member_id):
            raise DuplicateMembershipError(group_id, member_type, member_id)

        try:
            await self._db.execute(
                "INSERT INTO memberships (group_id, member_type, member_id) "
                "VALUES (?, ?, ?)",
                (group_id, member_type.value, member_id),
            )
        except aiosqlite.IntegrityError as exc:
            # Convert PK collision (race) into the domain exception.
            raise DuplicateMembershipError(group_id, member_type, member_id) from exc
        await self._db.commit()

    async def remove_member(
        self, group_id: int, member_type: SubjectType, member_id: int
    ) -> None:
        if not isinstance(member_type, SubjectType):
            raise TypeError("member_type must be a SubjectType")
        cursor = await self._db.execute(
            "DELETE FROM memberships WHERE group_id = ? AND member_type = ? "
            "AND member_id = ?",
            (group_id, member_type.value, member_id),
        )
        if cursor.rowcount == 0:
            raise MembershipNotFoundError(group_id, member_type, member_id)
        await self._db.commit()

    async def list_group_members(self, group_id: int) -> list[Membership]:
        await self.get_group_by_id(group_id)
        async with self._db.execute(
            "SELECT group_id, member_type, member_id FROM memberships "
            "WHERE group_id = ? ORDER BY member_type, member_id",
            (group_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            Membership(
                group_id=r[0],
                member_type=SubjectType(r[1]),
                member_id=r[2],
            )
            for r in rows
        ]

    async def list_parent_group_ids(
        self, member_type: SubjectType, member_id: int
    ) -> list[int]:
        if not isinstance(member_type, SubjectType):
            raise TypeError("member_type must be a SubjectType")
        async with self._db.execute(
            "SELECT group_id FROM memberships WHERE member_type = ? AND member_id = ?",
            (member_type.value, member_id),
        ) as cursor:
            rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def resolve_user_group_ids(self, user_id: int) -> set[int]:
        # Single algorithm lives in accounts.resolve.
        return await resolve_user_groups(self, user_id)

    # ------------------------------------------------------------------
    # Per-user quota
    # ------------------------------------------------------------------

    async def set_user_quota(self, user_id: int, quota_bytes: int) -> None:
        if not isinstance(quota_bytes, int) or quota_bytes < 0:
            raise ValueError("quota_bytes must be a non-negative integer")
        await self.get_user_by_id(user_id)
        await self._db.execute(
            "INSERT OR REPLACE INTO user_quota (user_id, quota_bytes) VALUES (?, ?)",
            (user_id, quota_bytes),
        )
        await self._db.commit()

    async def get_user_quota(self, user_id: int) -> int:
        async with self._db.execute(
            "SELECT quota_bytes FROM user_quota WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            raise QuotaNotSetError(user_id)
        return int(row[0])

    async def close(self) -> None:
        await self._db.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_user(row: aiosqlite.Row | tuple[Any, ...]) -> User:
        return User(
            id=row[0],
            username=row[1],
            email=row[2],
            password_hash=bytes(row[3]),
            created_at=row[4],
            is_active=bool(row[5]),
        )

    async def _username_exists(self, username: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def _group_name_exists(self, name: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM groups WHERE name = ?", (name,)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def _membership_exists(
        self, group_id: int, member_type: SubjectType, member_id: int
    ) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM memberships WHERE group_id = ? AND member_type = ? "
            "AND member_id = ?",
            (group_id, member_type.value, member_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def _group_descendants(self, group_id: int) -> set[int]:
        """Return all group ids transitively contained by ``group_id``.

        Walks GROUP membership edges downward; visited-set guards against
        any pre-existing corruption looping forever.
        """
        descendants: set[int] = set()
        frontier: list[int] = [group_id]
        while frontier:
            current = frontier.pop()
            async with self._db.execute(
                "SELECT member_id FROM memberships "
                "WHERE group_id = ? AND member_type = ?",
                (current, SubjectType.GROUP.value),
            ) as cursor:
                rows = await cursor.fetchall()
            for (child_id,) in rows:
                if child_id in descendants:
                    continue
                descendants.add(child_id)
                frontier.append(child_id)
        return descendants
