"""Agent WebSocket endpoint — accepts tunnel connections and registers mounts."""

import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

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
) -> None:
    """Accept an agent WebSocket connection and manage its tunnel lifecycle.

    - Accepts the WebSocket upgrade.
    - Determines the mount code: uses the preferred code if provided and not
      already occupied, otherwise generates a new one.
    - Wraps the socket in a TunnelConnection and registers it in the registry.
    - Sends a 'mount_registered' control message with the assigned code.
    - Starts the heartbeat and runs the receive loop until disconnect.
    - On any disconnect, deregisters the mount and closes the connection.

    Args:
        websocket: The FastAPI WebSocket connection from the agent.
        code:      Optional preferred mount code — reused for reconnect if available.
                   If None or already occupied, a fresh code is generated.
    """
    await websocket.accept()

    registry = get_registry()
    if code is not None and not registry.has_mount(code):
        assigned_code = code
    else:
        assigned_code = generate_mount_code()

    # Extract agent IP from X-Forwarded-For (Cloud Run) or direct connection
    client_ip: str = websocket.headers.get(
        "x-forwarded-for",
        websocket.client.host if websocket.client else "unknown",
    )

    conn = TunnelConnection(websocket)
    now: float = time.monotonic()
    registry.register(
        assigned_code,
        conn,
        agent_ip=client_ip,
        created_at=now,
        expires_at=None,
    )
    reused_code: bool = code is not None and assigned_code == code
    logger.info(
        "Agent connected: code=%s preferred_reuse=%s client=%s",
        assigned_code,
        reused_code,
        client_ip,
    )
    await conn.send_control({"type": "mount_registered", "code": assigned_code})
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
