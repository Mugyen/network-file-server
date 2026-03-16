"""Mount registry service — tracks active relay tunnel connections by mount code."""

import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from relay.app.enums import MountStatus
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError

if TYPE_CHECKING:
    from tunnel.connection import TunnelConnection


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


class MountRegistry:
    """In-memory registry of active relay mounts.

    Mounts are keyed by their URL-safe mount code. The registry enforces
    typed exceptions for all lifecycle state violations.
    """

    def __init__(self) -> None:
        self._mounts: dict[str, MountRecord] = {}

    def register(self, code: str, connection: "TunnelConnection") -> None:
        """Register a tunnel connection under the given mount code.

        Raises ValueError if code is empty. Overwrites any existing record
        for the same code.
        """
        if not code:
            raise ValueError("Mount code must not be empty")
        self._mounts[code] = MountRecord(
            code=code,
            connection=connection,
            status=MountStatus.ONLINE,
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


_registry: MountRegistry | None = None


def get_registry() -> MountRegistry:
    """Return the global MountRegistry instance.

    Raises RuntimeError if set_registry() has not been called.
    """
    if _registry is None:
        raise RuntimeError("MountRegistry has not been initialized. Call set_registry() first.")
    return _registry


def set_registry(registry: MountRegistry) -> None:
    """Install the global MountRegistry instance.

    Called by the app factory and by tests to inject a fresh instance.
    """
    global _registry
    _registry = registry
