"""File-TTL provider seam — dependency inversion between server and relay.

File TTLs are a relay-mount concept (the relay imposes expiry on uploaded
files), but the server renders them in listings and records them on upload.
The server therefore owns this small interface and whoever hosts the server
in-process (today: the relay's drop box) injects an implementation by
setting ``app.state.file_ttl_provider`` after building the app. Standalone
LAN mode leaves it None and the feature is cleanly absent — by explicit
configuration, not by a failed cross-package import.

The relay's FileTtlDb satisfies this protocol structurally (no inheritance,
no import of relay code here).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class FileTtlProvider(Protocol):
    """What the server needs from a TTL backend."""

    async def get_ttl_for_mount(self, mount_code: str) -> list[tuple[str, float]]:
        """Return (file_path, expires_at_epoch) for all files in a mount."""
        ...

    async def record_file_ttl(
        self, mount_code: str, file_path: str, ttl_seconds: int
    ) -> None:
        """Record (or overwrite) the TTL for one file."""
        ...
