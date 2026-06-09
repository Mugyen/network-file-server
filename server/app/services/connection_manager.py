"""WebSocket connection tracking and broadcast service."""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from fastapi import WebSocket

from server.app.models.enums import DeviceType


def parse_device_type(user_agent: str) -> DeviceType:
    """Classify device type from User-Agent string.

    Tablet check comes before phone check because some tablet UAs contain 'mobile'.
    """
    ua_lower = user_agent.lower()
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return DeviceType.TABLET
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return DeviceType.PHONE
    return DeviceType.DESKTOP


@dataclass(frozen=True)
class DeviceInfo:
    """Metadata for a connected device."""
    device_id: str
    device_name: str
    ip_address: str
    device_type: str
    connected_at: str


class ConnectionManager:
    """Manages active WebSocket connections, device tracking, and message broadcasting."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.devices: dict[str, DeviceInfo] = {}

    async def connect(self, websocket: WebSocket, device_id: str, device_name: str, ip_address: str, user_agent: str) -> None:
        """Accept WebSocket and register the device with metadata."""
        await websocket.accept()
        self.active_connections[device_id] = websocket
        device_type = parse_device_type(user_agent)
        info = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            device_type=device_type.value,
            connected_at=datetime.now(timezone.utc).isoformat(),
        )
        self.devices[device_id] = info

    def disconnect(self, device_id: str) -> None:
        """Remove a device from tracking."""
        self.active_connections.pop(device_id, None)
        self.devices.pop(device_id, None)

    def is_current_connection(self, device_id: str, websocket: WebSocket) -> bool:
        """True if this websocket is the one currently registered for device_id.

        With stable client-supplied device IDs, a second tab from the same
        browser replaces the first tab's registration. The first tab's
        teardown must not evict the newer connection, so callers check this
        before disconnect().
        """
        return self.active_connections.get(device_id) is websocket

    async def broadcast(self, message: dict, exclude_device: str) -> None:
        """Send message to all connections except excluded device_id.

        Dead connections that raise on send are removed automatically.
        """
        dead: list[str] = []
        for dev_id, ws in list(self.active_connections.items()):
            if dev_id == exclude_device:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(dev_id)
        for dev_id in dead:
            self.disconnect(dev_id)

    async def broadcast_all(self, message: dict) -> None:
        """Send message to all connections (no exclusion).

        Dead connections that raise on send are removed automatically.
        """
        dead: list[str] = []
        for dev_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(dev_id)
        for dev_id in dead:
            self.disconnect(dev_id)

    async def send_to(self, device_id: str, message: dict) -> None:
        """Send message to a specific device. Raises KeyError if not connected."""
        if device_id not in self.active_connections:
            raise KeyError(f"Device {device_id} not connected")
        await self.active_connections[device_id].send_json(message)

    def device_count(self) -> int:
        """Return the number of active connections."""
        return len(self.active_connections)

    def get_device_name(self, device_id: str) -> str:
        """Return the human-readable name for a device_id."""
        if device_id not in self.devices:
            raise KeyError(f"Device {device_id} not found")
        return self.devices[device_id].device_name

    def get_device_list(self) -> list[dict]:
        """Return list of device info dicts for all connected devices."""
        return [asdict(info) for info in self.devices.values()]

