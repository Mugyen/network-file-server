"""Agent WebSocket endpoint — accepts tunnel connections and registers mounts.

Includes mount registration rate limiting via the `limits` library directly
(SlowAPI decorators do not work on WebSocket endpoints), and per-IP mount
cap enforcement.
"""

import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from limits import parse as parse_limit
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from relay.app.config import get_config
from relay.app.exceptions import MountNotFoundError
from relay.app.services.mount_registry import generate_mount_code, get_registry
from tunnel.connection import TunnelConnection
from tunnel.constants import HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT

logger = logging.getLogger("relay.agent")

router = APIRouter()


async def _handle_agent_control_for_mount(msg: dict, mount_code: str) -> None:
    """Handle delete_expired_files and keep_expired_files control messages.

    Both message types clear expired TTL records for the mount so the agent
    is not re-prompted on the next reconnect.

    Args:
        msg: Parsed control message dict with at least a "type" key.
        mount_code: The mount code this agent connection is registered under.
    """
    msg_type = msg.get("type")
    if msg_type in ("delete_expired_files", "keep_expired_files"):
        try:
            from relay.app.services.file_ttl_db import get_file_ttl_db
            file_ttl_db = get_file_ttl_db()
            code = msg.get("code", mount_code)
            await file_ttl_db.delete_expired_for_mount(code)
            logger.info("Processed %s for mount=%s", msg_type, code)
        except RuntimeError:
            pass  # FileTtlDb not initialized -- no-op


# Module-level rate limiter for mount registration.
# Uses the `limits` library directly because SlowAPI decorators
# do not work on WebSocket endpoints.
_mount_reg_storage = MemoryStorage()
_mount_reg_limiter = MovingWindowRateLimiter(_mount_reg_storage)


def reset_mount_reg_limiter() -> None:
    """Reinitialize the mount registration rate limiter storage.

    Called by tests to avoid cross-test state pollution.
    """
    global _mount_reg_storage, _mount_reg_limiter
    _mount_reg_storage = MemoryStorage()
    _mount_reg_limiter = MovingWindowRateLimiter(_mount_reg_storage)


@router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    code: str | None = Query(None),
    ttl: int | None = Query(None),
) -> None:
    """Accept an agent WebSocket connection and manage its tunnel lifecycle.

    Order of checks (all before the main accept/register flow):
    1. Extract agent IP from headers (available before accept).
    2. Get config.
    3. Check mount registration rate limit (limits library).
    4. If rate limited: accept, send error, close, return.
    5. Hit rate limit counter (consume token).
    6. Check per-IP mount cap (registry query).
    7. If at cap: accept, send error, close, return.
    8. Accept WebSocket.
    9. Determine code, compute TTL, register, send mount_registered, run loop.

    Args:
        websocket: The FastAPI WebSocket connection from the agent.
        code:      Optional preferred mount code -- reused for reconnect if available.
                   If None or already occupied, a fresh code is generated.
        ttl:       Optional TTL in seconds. Capped to config.max_ttl_seconds.
                   If None, config.max_ttl_seconds is used.
    """
    # Extract agent IP from X-Forwarded-For (Cloud Run) or direct connection
    forwarded: str | None = websocket.headers.get("x-forwarded-for")
    if forwarded:
        client_ip: str = forwarded.split(",")[0].strip()
    else:
        client_ip = websocket.client.host if websocket.client else "unknown"

    config = get_config()
    registry = get_registry()

    # --- Reserved code check (before rate limit to avoid wasting tokens) ---
    if code is not None and code == config.dropbox_code:
        logger.warning(
            "Agent tried to register reserved drop box code: client=%s code=%s",
            client_ip, code,
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Reserved mount code",
        })
        await websocket.close(code=1008)
        return

    # --- Rate limit check (before accepting WebSocket) ---
    mount_limit = parse_limit(config.mount_reg_rate)
    if not _mount_reg_limiter.test(mount_limit, "mount_reg", client_ip):
        logger.warning(
            "Mount registration rate limited: client=%s", client_ip
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Rate limit exceeded",
            "retry_after": 3600,
        })
        await websocket.close(code=1008)
        return

    # Consume a rate limit token
    _mount_reg_limiter.hit(mount_limit, "mount_reg", client_ip)

    # --- Per-IP mount cap check ---
    current_count: int = await registry.count_mounts_by_ip(client_ip)
    if current_count >= config.max_mounts_per_ip:
        logger.warning(
            "Mount cap exceeded: client=%s count=%d",
            client_ip,
            current_count,
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Too many active mounts",
            "max": config.max_mounts_per_ip,
        })
        await websocket.close(code=1008)
        return

    # --- Normal mount registration flow ---
    await websocket.accept()

    # Determine assigned code with reclaim-aware logic
    reclaimed: bool = False
    remaining_ttl: int | None = None
    conn = TunnelConnection(websocket)

    if code is not None:
        reclaim_result = await registry.try_reclaim(code, conn, client_ip)
        if reclaim_result is not None:
            assigned_code = code
            reclaimed = True
            remaining_ttl = reclaim_result.remaining_ttl
        elif not await registry.has_mount(code):
            assigned_code = code
        else:
            assigned_code = generate_mount_code()
    else:
        assigned_code = generate_mount_code()

    # For non-reclaimed mounts: compute TTL and register
    if not reclaimed:
        effective_ttl: int = min(ttl, config.max_ttl_seconds) if ttl is not None else config.max_ttl_seconds
        now: float = time.time()
        expires_at: float = now + effective_ttl

        await registry.register(
            assigned_code,
            conn,
            agent_ip=client_ip,
            created_at=now,
            expires_at=expires_at,
        )
        expires_in: int = effective_ttl
    else:
        effective_ttl = remaining_ttl if remaining_ttl is not None else 0
        expires_in = effective_ttl

    reused_code: bool = code is not None and assigned_code == code
    logger.info(
        "Agent connected: code=%s preferred_reuse=%s reclaimed=%s client=%s ttl=%d",
        assigned_code,
        reused_code,
        reclaimed,
        client_ip,
        effective_ttl,
    )
    await conn.send_control({
        "type": "mount_registered",
        "code": assigned_code,
        "ttl": effective_ttl,
        "expires_in": expires_in,
        "reclaimed": reclaimed,
        "remaining_ttl": remaining_ttl,
    })
    # Send expired files list to agent on reclaim so it can prompt user
    if reclaimed:
        try:
            from relay.app.services.file_ttl_db import get_file_ttl_db
            file_ttl_db = get_file_ttl_db()
            expired = await file_ttl_db.get_expired_for_mount(assigned_code)
            if expired:
                await conn.send_control({
                    "type": "expired_files",
                    "code": assigned_code,
                    "files": [{"path": fp, "expired_at": exp} for fp, exp in expired],
                })
        except RuntimeError:
            pass  # FileTtlDb not initialized

    async def _on_agent_control(msg: dict) -> None:
        """Handle application-specific control messages from the agent.

        delete_expired_files: agent deleted expired files, clear TTL records.
        keep_expired_files: user chose to keep files, clear TTL records so
        they are not re-prompted on next reconnect.
        """
        await _handle_agent_control_for_mount(msg, assigned_code)

    conn.set_control_handler(_on_agent_control)
    conn.start_heartbeat(HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)
    try:
        await conn.run_receive_loop()
    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Agent disconnected: code=%s", assigned_code)
        await conn.close()
        try:
            await registry.mark_offline(assigned_code)
        except MountNotFoundError:
            pass
