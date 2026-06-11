"""Local ASGI mounts — mounts served in-process instead of through a tunnel.

A LocalAsgiMount wraps an ASGI app (e.g. the drop box's embedded file
server) together with the httpx client used to forward HTTP requests to it
and the WebSocket bridging logic. The proxy dispatches on membership in
``RelayState.local_mounts`` — it has no knowledge of *which* local mounts
exist (the drop box is just the one the lifespan happens to create).

Plan deviation note: the remediation plan sketched a persisted MountKind
enum on registry rows. Live ASGI apps cannot be persisted; the registry
already encodes locality as ``connection=None``, and the live object lives
here. Presence in ``local_mounts`` IS the mount kind.
"""

import asyncio
import logging
from typing import Any

import httpx
import httpx_ws
from fastapi import WebSocket
from httpx import ASGITransport, AsyncClient
from httpx_ws.transport import ASGIWebSocketTransport
from wsproto.events import BytesMessage, CloseConnection, TextMessage

logger = logging.getLogger("relay.local_mount")


class LocalAsgiMount:
    """An in-process mount: ASGI app + forwarding client + WS bridge."""

    def __init__(self, code: str, app: Any) -> None:
        if not isinstance(code, str) or len(code) == 0:
            raise ValueError("code must be a non-empty string")
        if app is None:
            raise ValueError("app must be an ASGI application, got None")
        self.code = code
        self.app = app
        self.client: AsyncClient = AsyncClient(
            transport=ASGITransport(app=app), base_url=f"http://{code}"
        )

    async def aclose(self) -> None:
        """Release the forwarding client. The app itself has no lifecycle."""
        await self.client.aclose()

    async def forward_request(
        self, method: str, path: str, headers: dict[str, str], content: bytes,
        query: str,
    ) -> httpx.Response:
        """Forward an HTTP request to the local app and return its response."""
        return await self.client.request(
            method=method,
            url=f"/{path}",
            headers=headers,
            content=content,
            params=query if query else None,
        )

    async def bridge_websocket(
        self, websocket: WebSocket, path: str, query: str,
        forward_headers: dict[str, str],
    ) -> None:
        """Bridge an accepted browser WebSocket to the local app's WebSocket.

        Runs until either side disconnects; never raises — bridge failures
        are logged and the browser socket is left to close naturally.
        """
        local_ws_url = f"ws://{self.code}/{path}"
        if query:
            local_ws_url = f"{local_ws_url}?{query}"
        try:
            async with ASGIWebSocketTransport(app=self.app) as ws_transport:
                async with httpx_ws.aconnect_ws(
                    local_ws_url,
                    httpx.AsyncClient(transport=ws_transport),
                    headers=forward_headers,
                    keepalive_ping_interval_seconds=None,
                ) as local_ws:

                    async def browser_to_local() -> None:
                        """Forward browser messages (text or binary) to the local app."""
                        while True:
                            message = await websocket.receive()
                            if message["type"] == "websocket.disconnect":
                                return
                            text = message.get("text")
                            if text is not None:
                                await local_ws.send_text(text)
                                continue
                            data = message.get("bytes")
                            if data is not None:
                                await local_ws.send_bytes(data)

                    async def local_to_browser() -> None:
                        """Forward local app messages to browser, mirroring frame kind."""
                        while True:
                            event = await local_ws.receive()
                            if isinstance(event, TextMessage):
                                await websocket.send_text(event.data)
                            elif isinstance(event, BytesMessage):
                                await websocket.send_bytes(event.data)
                            elif isinstance(event, CloseConnection):
                                return

                    b2l = asyncio.create_task(browser_to_local())
                    l2b = asyncio.create_task(local_to_browser())
                    done, pending = await asyncio.wait(
                        {b2l, l2b}, return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in done:
                        exc = t.exception()
                        if exc is not None:
                            logger.debug(
                                "Local WS bridge task ended with error: "
                                "code=%s path=%s error=%r",
                                self.code, path, exc,
                            )
                    for t in pending:
                        t.cancel()
                        try:
                            await t
                        except asyncio.CancelledError:
                            pass  # Expected — we just cancelled it.
                        except Exception:
                            logger.exception(
                                "Local WS bridge task raised during cancellation: "
                                "code=%s path=%s",
                                self.code, path,
                            )
        except Exception:
            logger.exception(
                "Local WS bridge failed: code=%s path=%s", self.code, path
            )
