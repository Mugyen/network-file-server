"""WebSocket endpoint for real-time communication."""

import time
from dataclasses import asdict
from datetime import datetime, timezone
from http.cookies import SimpleCookie

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from server.app.config import get_server_config
from server.app.models.enums import ToastType, WSMessageType
from server.app.services.auth_service import get_token_service
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


def _make_device_list(your_device_id: str) -> dict:
    """Build a device_list message with all connected devices and caller's ID."""
    return {
        "type": WSMessageType.DEVICE_LIST.value,
        "devices": manager.get_device_list(),
        "your_device_id": your_device_id,
    }


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    device_name: str = Query(...),
) -> None:
    """WebSocket endpoint accepting device_name as query param.

    On connect: sends device_list to new client, broadcasts device_connected toast
    (with device_info) to others, device_count to all.
    On disconnect: broadcasts device_disconnected toast (with device_id) to others,
    updated count.
    Receive loop routes messages by type (skeleton for future handlers).
    """
    device_id = f"{device_name}-{int(time.time() * 1000)}"

    # Check WebSocket auth when password is enabled
    config = get_server_config()
    if config.password_hash is not None:
        cookie_header = ""
        for header_name, header_value in websocket.headers.raw:
            if header_name == b"cookie":
                cookie_header = header_value.decode("latin-1")
                break

        authenticated = False
        if cookie_header:
            cookie: SimpleCookie[str] = SimpleCookie()
            cookie.load(cookie_header)
            morsel = cookie.get("session")
            if morsel is not None:
                token_service = get_token_service()
                authenticated = token_service.validate_token(morsel.value)

        if not authenticated:
            await websocket.accept()
            await websocket.close(code=4001)
            return

    # Capture IP and User-Agent before connect
    ip_address = websocket.client.host if websocket.client else "unknown"
    user_agent = websocket.headers.get("user-agent", "")

    await manager.connect(websocket, device_id, device_name, ip_address, user_agent)
    try:
        # Send device_list to the newly connected client
        await manager.send_to(device_id, _make_device_list(device_id))

        # Broadcast connect toast (with device_info) to others
        toast = _make_toast(ToastType.DEVICE_CONNECTED, f"{device_name} connected", device_name)
        toast["device_info"] = asdict(manager.devices[device_id])
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
                # Silently ignore snippet updates in read-only mode
                if config.read_only:
                    continue
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
        # Capture device_id before disconnect removes it
        disconnected_device_id = device_id
        manager.disconnect(device_id)
        # Broadcast disconnect toast (with device_id) to remaining
        toast = _make_toast(ToastType.DEVICE_DISCONNECTED, f"{device_name} disconnected", device_name)
        toast["device_id"] = disconnected_device_id
        await manager.broadcast_all(toast)
        # Broadcast updated device count
        await manager.broadcast_all(_make_device_count())
