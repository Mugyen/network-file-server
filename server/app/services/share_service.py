"""Share link service for creating, validating, revoking, and listing share links.

Uses itsdangerous URLSafeTimedSerializer with a dedicated salt to produce
signed tokens that embed the shared file path and expire after a chosen TTL.
When a data directory is provided, active links are also persisted in SQLite
so they survive restarts.
"""

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner, URLSafeTimedSerializer

from server.app.models.enums import ShareTTL
from server.app.services.sqlite_store import ShareLinkRow, get_state_store


class _ClockedTimestampSigner(TimestampSigner):
    """TimestampSigner with an injectable clock.

    itsdangerous reads the wall clock internally for both signing and
    max_age checks; routing it through ``now_fn`` gives tests a seam to
    exercise expiry without mutating service internals.
    """

    now_fn: Callable[[], float] = time.time

    def get_timestamp(self) -> int:
        return int(type(self).now_fn())


@dataclass(frozen=True)
class ShareLinkRecord:
    """In-memory record of an active share link."""

    token: str
    file_path: str
    created_at: datetime
    ttl_seconds: int


class ShareLinkRevokedError(Exception):
    """Raised when a share link token has been revoked."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link has been revoked: {token}")


class ShareLinkNotFoundError(Exception):
    """Raised when a share link token is not found in the registry."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link not found: {token}")


class ShareLinkExpiredError(Exception):
    """Raised when a share link token has expired."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link has expired: {token}")


class ShareLinkService:
    """Creates, validates, revokes, and lists expiring share links.

    Tokens are signed with itsdangerous using a dedicated salt separate
    from auth session tokens. Active links are tracked in-memory and
    persisted in SQLite when a data directory is available.
    """

    SALT = "share-link"

    def __init__(
        self,
        secret_key: str,
        data_dir: Path | None = None,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        # Per-instance signer class so each service can have its own clock
        # (the signer is instantiated by itsdangerous per operation).
        signer_cls = type("_Signer", (_ClockedTimestampSigner,), {"now_fn": staticmethod(now_fn)})
        self._now_fn = now_fn
        self._serializer = URLSafeTimedSerializer(secret_key, signer=signer_cls)
        # Guards _active_links: routes may run on multiple threads (sync
        # routes use the threadpool). Same pattern as ServerStateStore.
        self._lock = threading.RLock()
        self._active_links: dict[str, ShareLinkRecord] = {}
        self._store = get_state_store(data_dir) if data_dir is not None else None
        if self._store is not None:
            for row in self._store.list_share_links():
                self._active_links[row.token] = ShareLinkRecord(
                    token=row.token,
                    file_path=row.file_path,
                    created_at=datetime.fromisoformat(row.created_at),
                    ttl_seconds=row.ttl_seconds,
                )

    def create_link(self, file_path: str, ttl: ShareTTL) -> ShareLinkRecord:
        """Create a new share link for the given file path.

        Returns the full ShareLinkRecord (token, path, created_at, ttl) so
        callers never reach into the service's internal registry.
        """
        token: str = self._serializer.dumps({"path": file_path}, salt=self.SALT)
        now = datetime.fromtimestamp(self._now_fn(), tz=timezone.utc)
        record = ShareLinkRecord(
            token=token,
            file_path=file_path,
            created_at=now,
            ttl_seconds=int(ttl),
        )
        with self._lock:
            self._active_links[token] = record
            if self._store is not None:
                self._store.upsert_share_link(
                    ShareLinkRow(
                        token=token,
                        file_path=file_path,
                        created_at=now.isoformat(),
                        ttl_seconds=int(ttl),
                    )
                )
        return record

    def validate_token(self, token: str) -> str:
        """Validate a share link token and return the embedded file path.

        Raises ShareLinkRevokedError if the token was revoked.
        Raises ShareLinkExpiredError if the token has expired.
        Raises BadSignature if the token is tampered or invalid.
        """
        with self._lock:
            if token not in self._active_links:
                raise ShareLinkRevokedError(token)
            record = self._active_links[token]

        try:
            data: dict[str, str] = self._serializer.loads(
                token, salt=self.SALT, max_age=record.ttl_seconds
            )
        except SignatureExpired:
            # Clean up expired entry
            with self._lock:
                self._active_links.pop(token, None)
                if self._store is not None:
                    try:
                        self._store.delete_share_link(token)
                    except KeyError:
                        pass  # Already removed from SQLite — nothing to clean.
            raise ShareLinkExpiredError(token)

        return data["path"]

    def revoke_link(self, token: str) -> None:
        """Revoke a share link by removing it from the active registry.

        Raises ShareLinkNotFoundError if the token is not in the registry.
        """
        with self._lock:
            if token not in self._active_links:
                raise ShareLinkNotFoundError(token)
            del self._active_links[token]
            if self._store is not None:
                try:
                    self._store.delete_share_link(token)
                except KeyError:
                    pass  # Already removed from SQLite — nothing to clean.

    def list_active_links(self) -> list[ShareLinkRecord]:
        """Return all non-expired active share links.

        Filters out naturally expired entries during listing.
        """
        active: list[ShareLinkRecord] = []
        expired_tokens: list[str] = []

        with self._lock:
            snapshot = list(self._active_links.items())

        for token, record in snapshot:
            try:
                self._serializer.loads(
                    token, salt=self.SALT, max_age=record.ttl_seconds
                )
                active.append(record)
            except SignatureExpired:
                expired_tokens.append(token)
            except BadSignature:
                expired_tokens.append(token)

        with self._lock:
            for token in expired_tokens:
                self._active_links.pop(token, None)
                if self._store is not None:
                    try:
                        self._store.delete_share_link(token)
                    except KeyError:
                        pass  # Already removed from SQLite — nothing to clean.

        return active

