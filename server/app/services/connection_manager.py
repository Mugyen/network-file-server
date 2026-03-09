"""WebSocket connection tracking and broadcast service."""

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections, device tracking, and message broadcasting."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.device_names: dict[str, str] = {}

    async def connect(self, websocket: WebSocket, device_id: str, device_name: str) -> None:
        """Accept WebSocket and register the device."""
        await websocket.accept()
        self.active_connections[device_id] = websocket
        self.device_names[device_id] = device_name

    def disconnect(self, device_id: str) -> None:
        """Remove a device from tracking."""
        self.active_connections.pop(device_id, None)
        self.device_names.pop(device_id, None)

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
        if device_id not in self.device_names:
            raise KeyError(f"Device {device_id} not found")
        return self.device_names[device_id]


manager = ConnectionManager()
