"""WebSocket endpoint for real-time communication."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from server.app.models.enums import ToastType, WSMessageType
from server.app.services.clipboard_service import get_clipboard_service
from server.app.services.connection_manager import manager

router = APIRouter()


def _make_toast(toast_type: ToastType, message: str, device_name: str) -> dict:
    """Build a toast message dict."""
    return {
        "type": "toast",
        "toast_type": toast_type.value,
        "message": message,
        "device_name": device_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _make_device_count() -> dict:
    """Build a device_count message dict."""
    return {
        "type": "device_count",
        "count": manager.device_count(),
    }


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    device_name: str = Query(...),
) -> None:
    """WebSocket endpoint accepting device_name as query param.

    On connect: broadcasts device_connected toast to others, device_count to all.
    On disconnect: broadcasts device_disconnected toast to others, updated count.
    Receive loop routes messages by type (skeleton for future handlers).
    """
    device_id = f"{device_name}-{int(time.time() * 1000)}"

    await manager.connect(websocket, device_id, device_name)
    try:
        # Broadcast connect toast to others
        toast = _make_toast(ToastType.DEVICE_CONNECTED, f"{device_name} connected", device_name)
        await manager.broadcast(toast, device_id)
        # Broadcast device count to all
        await manager.broadcast_all(_make_device_count())

        while True:
            data = await websocket.receive_json()
            # Route by message type
            msg_type = data.get("type", "")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == WSMessageType.SNIPPET_UPDATE.value:
                snippet_id = data["snippet_id"]
                content = data["content"]
                service = get_clipboard_service()
                try:
                    updated = await service.update_snippet(snippet_id, content)
                    await manager.broadcast(
                        {
                            "type": WSMessageType.SNIPPET_UPDATED.value,
                            "snippet": updated.model_dump(),
                        },
                        device_id,
                    )
                except (KeyError, ValueError):
                    pass  # Silently ignore invalid updates
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(device_id)
        # Broadcast disconnect toast to remaining
        toast = _make_toast(ToastType.DEVICE_DISCONNECTED, f"{device_name} disconnected", device_name)
        await manager.broadcast_all(toast)
        # Broadcast updated device count
        await manager.broadcast_all(_make_device_count())
