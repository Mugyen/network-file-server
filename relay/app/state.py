"""Per-app relay state container.

Replaces the former module-level singletons (config, registry, session,
account store, file-TTL db, drop box client/app, mount-registration rate
limiter). One ``RelayState`` is attached to ``app.state.relay`` by
``create_relay_app``; lifespan fills in the async-constructed resources.

Lifecycle:
- ``config`` and the rate limiter exist from app construction.
- ``registry``, ``account_store``, ``session``, ``file_ttl_db``,
  ``dropbox_client``/``dropbox_app`` are created in lifespan (they need an
  event loop) and are ``None`` before it runs. Tests that bypass lifespan
  (httpx.ASGITransport) set these fields directly.

Accessors with ``require_`` prefixes raise RuntimeError instead of
returning None so call sites fail loudly when wiring is missing.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from relay.app.config import RelayConfig

if TYPE_CHECKING:
    from httpx import AsyncClient

    from accounts import SqliteAccountStore
    from relay.app.services.file_ttl_db import FileTtlDb
    from relay.app.services.session import RelaySession
    from relay.app.services.sqlite_registry import SqliteMountRegistry


def _default_storage() -> MemoryStorage:
    return MemoryStorage()


@dataclass
class RelayState:
    """All per-app-instance relay services. See module docstring."""

    config: RelayConfig
    registry: "SqliteMountRegistry | None" = None
    session: "RelaySession | None" = None
    account_store: "SqliteAccountStore | None" = None
    file_ttl_db: "FileTtlDb | None" = None
    dropbox_client: "AsyncClient | None" = None
    dropbox_app: Any = None
    mount_reg_storage: MemoryStorage = field(default_factory=_default_storage)
    mount_reg_limiter: MovingWindowRateLimiter = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.config, RelayConfig):
            raise ValueError(f"config must be a RelayConfig, got {type(self.config)!r}")
        self.mount_reg_limiter = MovingWindowRateLimiter(self.mount_reg_storage)

    # -- loud accessors (rule: fail with a typed error, never hand out None) --

    def require_registry(self) -> "SqliteMountRegistry":
        """Return the mount registry or raise if lifespan has not wired it."""
        if self.registry is None:
            raise RuntimeError("RelayState.registry is not wired (lifespan not run?)")
        return self.registry

    def require_session(self) -> "RelaySession":
        """Return the session signer or raise if not wired."""
        if self.session is None:
            raise RuntimeError("RelayState.session is not wired (lifespan not run?)")
        return self.session

    def require_account_store(self) -> "SqliteAccountStore":
        """Return the account store or raise if not wired."""
        if self.account_store is None:
            raise RuntimeError(
                "RelayState.account_store is not wired (lifespan not run?)"
            )
        return self.account_store

    def require_file_ttl_db(self) -> "FileTtlDb":
        """Return the file-TTL db or raise if not wired."""
        if self.file_ttl_db is None:
            raise RuntimeError(
                "RelayState.file_ttl_db is not wired (lifespan not run?)"
            )
        return self.file_ttl_db
