"""WebSocket adapter wrapping a websockets ClientConnection.

Satisfies the tunnel.protocol.WebSocketProtocol structural interface so that
TunnelConnection can be used with the agent's outbound WebSocket connection.
"""

from websockets.asyncio.client import ClientConnection


class WebSocketClientAdapter:
    """Adapter that wraps a websockets ClientConnection to satisfy WebSocketProtocol.

    Bridges the websockets library's ClientConnection API to the tunnel's
    WebSocketProtocol interface (send_bytes/send_text/receive_bytes/receive_text/receive).

    Args:
        ws: A websockets.asyncio.client.ClientConnection instance.

    Raises:
        TypeError: If ws is not a ClientConnection instance.
    """

    def __init__(self, ws: ClientConnection) -> None:
        if not isinstance(ws, ClientConnection):
            raise TypeError(
                f"ws must be a websockets ClientConnection, got {type(ws).__name__}"
            )
        self._ws = ws

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary WebSocket frame.

        Args:
            data: Raw bytes to send.
        """
        await self._ws.send(data)

    async def send_text(self, data: str) -> None:
        """Send a text WebSocket frame.

        Args:
            data: UTF-8 string to send.
        """
        await self._ws.send(data)

    async def receive_bytes(self) -> bytes:
        """Receive the next binary WebSocket frame.

        Returns:
            The received bytes.

        Raises:
            TypeError: If the received message is not bytes.
        """
        result = await self._ws.recv(decode=False)
        if not isinstance(result, bytes):
            raise TypeError(
                f"Expected bytes from WebSocket, got {type(result).__name__}"
            )
        return result

    async def receive_text(self) -> str:
        """Receive the next text WebSocket frame.

        Returns:
            The received string.

        Raises:
            TypeError: If the received message is not a str.
        """
        result = await self._ws.recv(decode=True)
        if not isinstance(result, str):
            raise TypeError(
                f"Expected str from WebSocket, got {type(result).__name__}"
            )
        return result

    async def receive(self) -> dict:
        """Receive the next WebSocket frame as a typed dict.

        Returns:
            {'bytes': <bytes>} for binary frames or {'text': <str>} for text frames.
        """
        result = await self._ws.recv(decode=None)
        if isinstance(result, bytes):
            return {"bytes": result}
        return {"text": result}

    async def close(self) -> None:
        """Close the underlying WebSocket connection."""
        await self._ws.close()
