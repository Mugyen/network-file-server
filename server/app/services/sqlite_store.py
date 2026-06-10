"""SQLite-backed persistence for server collaboration state.

This store centralizes durable state for clipboard snippets, file requests,
share links, upload ownership, and persistent secrets. It uses a single
SQLite database under the server's data directory and keeps the schema
simple so feature services can stay thin.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


_DB_FILENAME = "server_state.db"
_META_SHARE_SECRET_KEY = "share_secret"


def state_db_path(data_dir: Path) -> Path:
    """Return the canonical SQLite path for the server state DB."""
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / _DB_FILENAME


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@dataclass(frozen=True)
class ClipboardRow:
    id: str
    title: str
    content: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class FileRequestRow:
    id: str
    description: str
    requester_device_id: str
    requester_device_name: str
    status: str
    created_at: str
    fulfilled_by_device_name: str | None
    fulfilled_file_name: str | None
    fulfilled_file_path: str | None
    fulfilled_at: str | None


@dataclass(frozen=True)
class ShareLinkRow:
    token: str
    file_path: str
    created_at: str
    ttl_seconds: int


class ServerStateStore:
    """Thin SQLite repository for all server collaboration state."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = _connect(db_path)
        self._lock = threading.RLock()
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            with self._conn:
                yield self._conn

    def _init_schema(self) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clipboard_snippets (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_requests (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    requester_device_id TEXT NOT NULL,
                    requester_device_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    fulfilled_by_device_name TEXT,
                    fulfilled_file_name TEXT,
                    fulfilled_file_path TEXT,
                    fulfilled_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS share_links (
                    token TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_owners (
                    rel_path TEXT PRIMARY KEY,
                    uploader TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    # --- Meta -----------------------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?",
                (key,),
            ).fetchone()
            return None if row is None else str(row["value"])

    def set_meta(self, key: str, value: str) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_or_create_share_secret(self) -> str:
        value = self.get_meta(_META_SHARE_SECRET_KEY)
        if value is not None:
            return value
        import secrets

        value = secrets.token_urlsafe(32)
        self.set_meta(_META_SHARE_SECRET_KEY, value)
        return value

    # --- Clipboard snippets ---------------------------------------------------

    def list_clipboard_snippets(self) -> list[ClipboardRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, content, created_at, updated_at "
                "FROM clipboard_snippets ORDER BY created_at ASC"
            ).fetchall()
            return [ClipboardRow(**dict(row)) for row in rows]

    def count_clipboard_snippets(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS count FROM clipboard_snippets"
            ).fetchone()
            return int(row["count"] if row is not None else 0)

    def insert_clipboard_snippet(self, row: ClipboardRow) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO clipboard_snippets(id, title, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row.id, row.title, row.content, row.created_at, row.updated_at),
            )

    def update_clipboard_snippet(self, snippet_id: str, *, title: str | None = None, content: str | None = None) -> ClipboardRow:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT id, title, content, created_at, updated_at "
                "FROM clipboard_snippets WHERE id = ?",
                (snippet_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Snippet '{snippet_id}' not found")
            next_title = title if title is not None else str(row["title"])
            next_content = content if content is not None else str(row["content"])
            updated_at = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE clipboard_snippets SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (next_title, next_content, updated_at, snippet_id),
            )
            return ClipboardRow(
                id=str(row["id"]),
                title=next_title,
                content=next_content,
                created_at=str(row["created_at"]),
                updated_at=updated_at,
            )

    def delete_clipboard_snippet(self, snippet_id: str) -> None:
        with self._transaction() as conn:
            cur = conn.execute(
                "DELETE FROM clipboard_snippets WHERE id = ?",
                (snippet_id,),
            )
            if cur.rowcount == 0:
                raise KeyError(f"Snippet '{snippet_id}' not found")

    # --- File requests --------------------------------------------------------

    def list_file_requests(self) -> list[FileRequestRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, description, requester_device_id, requester_device_name, "
                "status, created_at, fulfilled_by_device_name, fulfilled_file_name, "
                "fulfilled_file_path, fulfilled_at "
                "FROM file_requests "
                "WHERE status != 'dismissed' "
                "ORDER BY created_at DESC"
            ).fetchall()
            return [FileRequestRow(**dict(row)) for row in rows]

    def insert_file_request(self, row: FileRequestRow) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO file_requests(
                    id, description, requester_device_id, requester_device_name,
                    status, created_at, fulfilled_by_device_name, fulfilled_file_name,
                    fulfilled_file_path, fulfilled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.id,
                    row.description,
                    row.requester_device_id,
                    row.requester_device_name,
                    row.status,
                    row.created_at,
                    row.fulfilled_by_device_name,
                    row.fulfilled_file_name,
                    row.fulfilled_file_path,
                    row.fulfilled_at,
                ),
            )

    def get_file_request(self, request_id: str) -> FileRequestRow:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, description, requester_device_id, requester_device_name, "
                "status, created_at, fulfilled_by_device_name, fulfilled_file_name, "
                "fulfilled_file_path, fulfilled_at "
                "FROM file_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"File request '{request_id}' not found")
            return FileRequestRow(**dict(row))

    def update_file_request(
        self,
        request_id: str,
        *,
        status: str | None = None,
        fulfilled_by_device_name: str | None = None,
        fulfilled_file_name: str | None = None,
        fulfilled_file_path: str | None = None,
        fulfilled_at: str | None = None,
    ) -> FileRequestRow:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT id, description, requester_device_id, requester_device_name, "
                "status, created_at, fulfilled_by_device_name, fulfilled_file_name, "
                "fulfilled_file_path, fulfilled_at "
                "FROM file_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"File request '{request_id}' not found")
            next_status = status if status is not None else str(row["status"])
            next_fulfilled_by = (
                fulfilled_by_device_name
                if fulfilled_by_device_name is not None
                else row["fulfilled_by_device_name"]
            )
            next_fulfilled_name = (
                fulfilled_file_name
                if fulfilled_file_name is not None
                else row["fulfilled_file_name"]
            )
            next_fulfilled_path = (
                fulfilled_file_path
                if fulfilled_file_path is not None
                else row["fulfilled_file_path"]
            )
            next_fulfilled_at = fulfilled_at if fulfilled_at is not None else row["fulfilled_at"]
            conn.execute(
                """
                UPDATE file_requests
                SET status = ?, fulfilled_by_device_name = ?, fulfilled_file_name = ?,
                    fulfilled_file_path = ?, fulfilled_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    next_fulfilled_by,
                    next_fulfilled_name,
                    next_fulfilled_path,
                    next_fulfilled_at,
                    request_id,
                ),
            )
            return FileRequestRow(
                id=str(row["id"]),
                description=str(row["description"]),
                requester_device_id=str(row["requester_device_id"]),
                requester_device_name=str(row["requester_device_name"]),
                status=next_status,
                created_at=str(row["created_at"]),
                fulfilled_by_device_name=next_fulfilled_by,
                fulfilled_file_name=next_fulfilled_name,
                fulfilled_file_path=next_fulfilled_path,
                fulfilled_at=next_fulfilled_at,
            )

    def dismiss_file_request(self, request_id: str) -> None:
        with self._transaction() as conn:
            cur = conn.execute(
                "UPDATE file_requests SET status = 'dismissed' WHERE id = ?",
                (request_id,),
            )
            if cur.rowcount == 0:
                raise KeyError(f"File request '{request_id}' not found")

    # --- Share links ----------------------------------------------------------

    def list_share_links(self) -> list[ShareLinkRow]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT token, file_path, created_at, ttl_seconds FROM share_links"
            ).fetchall()
            return [ShareLinkRow(**dict(row)) for row in rows]

    def upsert_share_link(self, row: ShareLinkRow) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO share_links(token, file_path, created_at, ttl_seconds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET
                    file_path = excluded.file_path,
                    created_at = excluded.created_at,
                    ttl_seconds = excluded.ttl_seconds
                """,
                (row.token, row.file_path, row.created_at, row.ttl_seconds),
            )

    def delete_share_link(self, token: str) -> None:
        with self._transaction() as conn:
            cur = conn.execute(
                "DELETE FROM share_links WHERE token = ?",
                (token,),
            )
            if cur.rowcount == 0:
                raise KeyError(token)

    def get_share_link(self, token: str) -> ShareLinkRow | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT token, file_path, created_at, ttl_seconds FROM share_links WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                return None
            return ShareLinkRow(**dict(row))

    # --- Upload ownership -----------------------------------------------------

    def record_upload_owner(self, rel_path: str, uploader: str) -> None:
        with self._transaction() as conn:
            conn.execute(
                """
                INSERT INTO upload_owners(rel_path, uploader)
                VALUES (?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET uploader = excluded.uploader
                """,
                (rel_path, uploader),
            )

    def is_upload_owned_by(self, rel_path: str, uploader: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT uploader FROM upload_owners WHERE rel_path = ?",
                (rel_path,),
            ).fetchone()
            return row is not None and str(row["uploader"]) == uploader

    def owned_upload_paths(self, uploader: str) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT rel_path FROM upload_owners WHERE uploader = ?",
                (uploader,),
            ).fetchall()
            return {str(row["rel_path"]) for row in rows}


def open_state_store(data_dir: Path) -> ServerStateStore:
    """Create a new state store for the given data directory.

    Each app instance owns exactly one store (constructed in create_app and
    attached to ``app.state.store``); there is deliberately no process-level
    cache — two apps on the same data dir get independent connections (WAL
    mode handles concurrent access).
    """
    return ServerStateStore(state_db_path(data_dir))
