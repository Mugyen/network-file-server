"""Background file TTL sweep -- deletes expired files and broadcasts WebSocket notifications.

Runs as an asyncio background task alongside the mount TTL sweep.
Only deletes files for the drop box mount (relay has filesystem access).
For agent-backed mounts, records are cleaned up but files are not deleted
(the agent handles its own filesystem).
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, Coroutine

from relay.app.services.file_ttl_db import FileTtlDb

logger = logging.getLogger("relay.file_ttl_sweep")

BroadcastFn = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


async def file_ttl_sweep_once(
    file_ttl_db: FileTtlDb,
    data_dir: Path,
    dropbox_code: str,
    broadcast_fn: BroadcastFn | None,
) -> list[str]:
    """Single sweep iteration. Deletes expired drop box files and clears records.

    Returns list of deleted file paths (drop box only).
    """
    expired = await file_ttl_db.get_expired()
    deleted: list[str] = []
    for mount_code, file_path, _expires_at in expired:
        # Only delete files for the drop box (relay has filesystem access)
        if mount_code == dropbox_code:
            full_path = data_dir / "dropbox" / file_path.lstrip("/")
            if full_path.exists():
                try:
                    os.remove(full_path)
                    logger.info("Deleted expired file: %s (mount=%s)", file_path, mount_code)
                    deleted.append(file_path)
                except OSError:
                    logger.exception("Failed to delete expired file: %s", file_path)
        await file_ttl_db.delete_record(mount_code, file_path)

    # Broadcast toast for each deleted file
    if broadcast_fn is not None and deleted:
        for fp in deleted:
            await broadcast_fn({
                "type": "toast",
                "message": f"File expired and removed: {Path(fp).name}",
            })
    return deleted


async def run_file_ttl_sweep(
    file_ttl_db: FileTtlDb,
    data_dir: Path,
    dropbox_code: str,
    sweep_interval: int,
    broadcast_fn: BroadcastFn | None,
) -> None:
    """Run the file TTL sweep loop indefinitely."""
    while True:
        await asyncio.sleep(sweep_interval)
        await file_ttl_sweep_once(file_ttl_db, data_dir, dropbox_code, broadcast_fn)
