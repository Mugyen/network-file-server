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
