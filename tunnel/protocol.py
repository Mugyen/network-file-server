"""Framework-agnostic WebSocket protocol interface for the tunnel library."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class WebSocketProtocol(Protocol):
    """Structural interface that any WebSocket adapter must satisfy.

    Both the relay (FastAPI WebSocket) and tests (MockWebSocket) implement
    this protocol so the tunnel module never imports FastAPI directly.
    """

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary WebSocket frame."""
        ...

    async def send_text(self, data: str) -> None:
        """Send a text WebSocket frame."""
        ...

    async def receive_bytes(self) -> bytes:
        """Receive the next binary WebSocket frame."""
        ...

    async def receive_text(self) -> str:
        """Receive the next text WebSocket frame."""
        ...

    async def receive(self) -> dict:
        """Receive the next frame (binary or text).

        Returns a dict with exactly one key:
          - {"bytes": <bytes>}  for binary frames
          - {"text": <str>}     for text frames
        """
        ...
