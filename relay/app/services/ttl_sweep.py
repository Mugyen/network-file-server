"""Background TTL sweep — expires mounts past their TTL, warns before expiry, and cleans up retained records."""

import asyncio
import logging
import time

from relay.app.config import RelayConfig
from relay.app.enums import MountStatus
from relay.app.services.mount_registry import MountRecord
from relay.app.services.sqlite_registry import SqliteMountRegistry

logger = logging.getLogger("relay.ttl_sweep")


async def sweep_once(registry: SqliteMountRegistry, config: RelayConfig) -> None:
    """Run a single TTL sweep iteration over all active mounts.

    For each ONLINE mount with an expires_at:
    - If past expiry: call expire() to mark EXPIRED (retains record) and close the connection.
    - If within warning window and not yet warned: send ttl_warning control message.

    After per-mount processing, delete expired records past 6h retention window.

    Per-mount exceptions are caught to prevent one bad mount from killing the sweep.

    Args:
        registry: The SqliteMountRegistry to sweep.
        config: RelayConfig providing warning_before_seconds.
    """
    now: float = time.time()
    mounts: list[MountRecord] = await registry.active_mounts()

    for mount in mounts:
        if mount.expires_at is None:
            continue
        if mount.status != MountStatus.ONLINE:
            continue

        remaining: float = mount.expires_at - now
        try:
            if remaining <= 0:
                logger.info("TTL expired: code=%s", mount.code)
                await registry.expire(mount.code)
                if mount.connection is not None:
                    await mount.connection.close()
            elif remaining <= config.warning_before_seconds and not mount.ttl_warned:
                if mount.connection is not None:
                    await mount.connection.send_control(
                        {"type": "ttl_warning", "expires_in": int(remaining)}
                    )
                mount.ttl_warned = True
        except Exception:
            logger.exception(
                "Error processing mount during TTL sweep: code=%s", mount.code
            )

    # Retention cleanup: delete expired records past 6h retention window
    retention_cutoff: float = now - (6 * 3600)
    await registry.delete_expired_before(retention_cutoff)


async def run_ttl_sweep(registry: SqliteMountRegistry, config: RelayConfig) -> None:
    """Periodically sweep all mounts and expire those past their TTL.

    Runs forever until cancelled. Each iteration calls sweep_once() after
    sleeping for config.ttl_sweep_interval_seconds.

    Args:
        registry: The SqliteMountRegistry to sweep.
        config: RelayConfig providing sweep interval and warning settings.
    """
    while True:
        await asyncio.sleep(config.ttl_sweep_interval_seconds)
        await sweep_once(registry, config)
