"""Mount registry service — tracks active relay tunnel connections by mount code."""

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from accounts import AccessMode, Role, SubjectType
from relay.app.enums import MountStatus
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError

if TYPE_CHECKING:
    from tunnel.connection import TunnelConnection


@dataclass(frozen=True)
class PolicyEntry:
    """One allowlist entry for a mount: a subject and its granted role."""

    subject_type: SubjectType
    subject_id: int
    role: Role


@dataclass(frozen=True)
class MountPolicy:
    """Access policy bound to a mount code.

    owner_user_id is None for anonymous mounts (no --login). access_mode
    OPEN means anyone may access; RESTRICTED gates on the allowlist (with
    the per-mount password as the documented fallback, enforced in the
    proxy layer).
    """

    code: str
    owner_user_id: int | None
    access_mode: AccessMode
    has_password: bool
    entries: tuple[PolicyEntry, ...]


def generate_mount_code() -> str:
    """Return an 8-character URL-safe random mount code.

    Uses secrets.token_urlsafe(6) which produces exactly 8 base64url characters
    from 6 random bytes.
    """
    return secrets.token_urlsafe(6)


@dataclass
class MountRecord:
    """Stores mount metadata alongside the live tunnel connection."""

    code: str
    connection: "TunnelConnection"
    status: MountStatus
    agent_ip: str
    created_at: float
    expires_at: float | None
    ttl_warned: bool


class MountRegistry:
    """In-memory registry of active relay mounts.

    Mounts are keyed by their URL-safe mount code. The registry enforces
    typed exceptions for all lifecycle state violations.
    """

    def __init__(self) -> None:
        self._mounts: dict[str, MountRecord] = {}

    def register(
        self,
        code: str,
        connection: "TunnelConnection",
        agent_ip: str,
        created_at: float,
        expires_at: float | None,
    ) -> None:
        """Register a tunnel connection under the given mount code.

        Args:
            code: URL-safe mount code.
            connection: Live tunnel connection to the agent.
            agent_ip: IP address of the agent that created this mount.
            created_at: Monotonic timestamp of mount creation.
            expires_at: Monotonic timestamp when the mount expires, or None for no TTL.

        Raises:
            ValueError: If code is empty.
        """
        if not code:
            raise ValueError("Mount code must not be empty")
        self._mounts[code] = MountRecord(
            code=code,
            connection=connection,
            status=MountStatus.ONLINE,
            agent_ip=agent_ip,
            created_at=created_at,
            expires_at=expires_at,
            ttl_warned=False,
        )

    def deregister(self, code: str) -> None:
        """Remove the mount record for the given code.

        Raises MountNotFoundError if the code is not present.
        """
        if code not in self._mounts:
            raise MountNotFoundError(code)
        del self._mounts[code]

    def get_connection(self, code: str) -> "TunnelConnection":
        """Return the live TunnelConnection for a mount code.

        Raises:
            MountNotFoundError: code is not registered.
            MountOfflineError: mount is registered but OFFLINE.
            MountExpiredError: mount is registered but EXPIRED.
        """
        if code not in self._mounts:
            raise MountNotFoundError(code)
        record = self._mounts[code]
        if record.status == MountStatus.OFFLINE:
            raise MountOfflineError(code)
        if record.status == MountStatus.EXPIRED:
            raise MountExpiredError(code)
        return record.connection

    def mark_offline(self, code: str) -> None:
        """Transition a registered mount to OFFLINE status.

        Raises MountNotFoundError if the code is not present.
        """
        if code not in self._mounts:
            raise MountNotFoundError(code)
        self._mounts[code].status = MountStatus.OFFLINE

    def has_mount(self, code: str) -> bool:
        """Return True if a record exists for the given code, regardless of status."""
        return code in self._mounts

    def count_mounts_by_ip(self, agent_ip: str) -> int:
        """Count active (non-expired) mounts registered by this IP.

        Args:
            agent_ip: The IP address to count mounts for.

        Returns:
            Number of non-EXPIRED mounts held by the given IP.
        """
        return sum(
            1
            for m in self._mounts.values()
            if m.agent_ip == agent_ip and m.status != MountStatus.EXPIRED
        )

    def active_mounts(self) -> list[MountRecord]:
        """Return a snapshot of all non-EXPIRED mount records.

        Returns a list copy, not a view into the internal dict, so callers
        can iterate safely while the registry is mutated.
        """
        return [m for m in self._mounts.values() if m.status != MountStatus.EXPIRED]


if TYPE_CHECKING:
    from relay.app.services.sqlite_registry import SqliteMountRegistry

_registry: "MountRegistry | SqliteMountRegistry | None" = None


def get_registry() -> "MountRegistry | SqliteMountRegistry":
    """Return the global MountRegistry instance.

    Raises RuntimeError if set_registry() has not been called.
    """
    if _registry is None:
        raise RuntimeError("MountRegistry has not been initialized. Call set_registry() first.")
    return _registry


def set_registry(registry: "MountRegistry | SqliteMountRegistry") -> None:
    """Install the global MountRegistry instance.

    Called by the app factory and by tests to inject a fresh instance.
    """
    global _registry
    _registry = registry
