"""Agent WebSocket endpoint — accepts tunnel connections and registers mounts."""

import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from relay.app.config import get_config
from relay.app.exceptions import MountNotFoundError
from relay.app.services.mount_registry import generate_mount_code, get_registry
from tunnel.connection import TunnelConnection
from tunnel.constants import HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT

logger = logging.getLogger("relay.agent")

router = APIRouter()


@router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    code: str | None = Query(None),
    ttl: int | None = Query(None),
) -> None:
    """Accept an agent WebSocket connection and manage its tunnel lifecycle.

    - Extracts agent IP from headers.
    - Accepts the WebSocket upgrade.
    - Determines the mount code: uses the preferred code if provided and not
      already occupied, otherwise generates a new one.
    - Computes effective TTL (capped to config maximum).
    - Wraps the socket in a TunnelConnection and registers it in the registry.
    - Sends a 'mount_registered' control message with the assigned code and TTL.
    - Starts the heartbeat and runs the receive loop until disconnect.
    - On any disconnect, deregisters the mount and closes the connection.

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

    await websocket.accept()

    registry = get_registry()
    if code is not None and not registry.has_mount(code):
        assigned_code = code
    else:
        assigned_code = generate_mount_code()

    # Compute effective TTL -- cap to config maximum
    effective_ttl: int = min(ttl, config.max_ttl_seconds) if ttl is not None else config.max_ttl_seconds
    now: float = time.monotonic()
    expires_at: float = now + effective_ttl

    conn = TunnelConnection(websocket)
    registry.register(
        assigned_code,
        conn,
        agent_ip=client_ip,
        created_at=now,
        expires_at=expires_at,
    )
    reused_code: bool = code is not None and assigned_code == code
    logger.info(
        "Agent connected: code=%s preferred_reuse=%s client=%s ttl=%d",
        assigned_code,
        reused_code,
        client_ip,
        effective_ttl,
    )
    await conn.send_control({
        "type": "mount_registered",
        "code": assigned_code,
        "ttl": effective_ttl,
        "expires_in": effective_ttl,
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
            registry.deregister(assigned_code)
        except MountNotFoundError:
            pass
