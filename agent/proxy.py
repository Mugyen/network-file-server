"""Agent proxy — OPEN frame handler that dispatches requests to the local ASGI app.

Receives OPEN frame metadata from the relay, forwards the HTTP request to the
local FastAPI app via httpx ASGITransport, and streams DATA+CLOSE frames back.
Handles CANCEL (StreamNotFoundError) by exiting cleanly.

Also handles WS_OPEN frames by opening a local WebSocket to the ASGI app and
bridging messages bidirectionally between the relay tunnel and the local app.
"""

import asyncio
import json
import uuid
from typing import Any

import httpx
import httpx_ws
from httpx_ws.transport import ASGIWebSocketTransport

from agent.display import print_request_line
from tunnel.connection import TunnelConnection
from tunnel.constants import MAX_PAYLOAD_BYTES
from tunnel.exceptions import StreamNotFoundError


async def handle_open_frame(
    conn: TunnelConnection,
    request_id: uuid.UUID,
    metadata: dict,
    asgi_client: httpx.AsyncClient,
) -> None:
    """Proxy an OPEN frame to the local ASGI app and stream DATA+CLOSE back.

    Extracts HTTP request data from metadata, sends the request to the local
    app via asgi_client, then writes:
      1. First DATA frame: JSON-encoded {"status": ..., "headers": {...}}
      2. Subsequent DATA frames: response body in 65536-byte chunks
      3. CLOSE frame after all body chunks are sent

    If StreamNotFoundError is raised at any point (CANCEL received from relay),
    the handler exits cleanly without propagating the exception.

    Args:
        conn:        TunnelConnection to send DATA and CLOSE frames on.
        request_id:  UUID correlating this request to a relay stream.
        metadata:    Dict containing method, path, query, headers, content_length fields.
        asgi_client: httpx.AsyncClient backed by ASGITransport pointing at local app.
    """
    method: str = metadata["method"]
    path: str = metadata["path"]
    query: str = metadata.get("query", "")
    headers: dict = metadata.get("headers", {})

    # Build URL — append query string if present
    url = f"http://local{path}"
    if query:
        url = f"{url}?{query}"

    # Stream was already opened by the receive loop (before spawning this task) so that
    # DATA frames dispatched by subsequent loop iterations land in the queue.
    state = conn.get_stream(request_id)

    # Reconstruct request body from DATA frames (zero-length frame = end-of-body sentinel).
    # Read from the queue directly rather than read_stream_iter to avoid premature stream removal.
    body_parts: list[bytes] = []
    while True:
        chunk: bytes = await state.queue.get()
        if len(chunk) == 0:
            break
        body_parts.append(chunk)
    content: bytes = b"".join(body_parts)

    # Body fully received — remove the inbound stream registration.
    # The outbound DATA frames we send for the response go through conn.send_data(),
    # which does not use the local stream registry.
    conn.remove_stream(request_id)

    try:
        async with asgi_client.stream(method, url, headers=headers, content=content) as response:
            status_code = response.status_code

            # First DATA frame: response metadata (status + headers)
            meta_payload = json.dumps(
                {"status": status_code, "headers": dict(response.headers)}
            ).encode("utf-8")
            try:
                await conn.send_data(request_id, meta_payload)
            except StreamNotFoundError:
                return

            # Stream body chunks as subsequent DATA frames
            async for chunk in response.aiter_bytes(chunk_size=MAX_PAYLOAD_BYTES):
                if not chunk:
                    continue
                try:
                    await conn.send_data(request_id, chunk)
                except StreamNotFoundError:
                    return

            await conn.send_close(request_id)

        print_request_line(method, path, status_code)

    except StreamNotFoundError:
        return


async def handle_ws_open_frame(
    conn: TunnelConnection,
    ws_id: uuid.UUID,
    metadata: dict,
    app: Any,
) -> None:
    """Open a local WebSocket to the ASGI app and bridge messages bidirectionally.

    Reads metadata for the WebSocket path and query string, connects to the local
    ASGI app via httpx_ws and ASGIWebSocketTransport, then runs two concurrent tasks:
    - relay_to_local: reads WS_DATA from the tunnel stream, sends to local WS
    - local_to_relay: reads messages from the local WS, sends as WS_DATA to relay

    Sends WS_CLOSE to the relay in the finally block regardless of how the function exits.

    Args:
        conn:     TunnelConnection to read WS_DATA from and send WS_DATA/WS_CLOSE on.
        ws_id:    UUID of the WebSocket stream on the relay tunnel.
        metadata: Dict containing "path" and optional "query" from the WS_OPEN frame.
        app:      The ASGI application to connect the local WebSocket to.

    Raises:
        Does not raise — all exceptions are caught and WS_CLOSE is always sent.
    """
    path: str = metadata["path"]
    query: str = metadata.get("query", "")
    headers: dict[str, str] = metadata.get("headers", {})

    # Register the stream so read_stream_iter can receive WS_DATA frames
    conn.open_stream(ws_id)

    local_ws_url = f"ws://local{path}"
    if query:
        local_ws_url = f"{local_ws_url}?{query}"

    try:
        async with ASGIWebSocketTransport(app=app) as ws_transport:
            async with httpx_ws.aconnect_ws(
                local_ws_url,
                httpx.AsyncClient(transport=ws_transport),
                headers=headers,
                keepalive_ping_interval_seconds=None,
            ) as local_ws:

                async def relay_to_local() -> None:
                    """Forward WS_DATA frames from relay to the local WebSocket."""
                    async for chunk in conn.read_stream_iter(ws_id):
                        await local_ws.send_text(chunk.decode("utf-8"))

                async def local_to_relay() -> None:
                    """Forward local WebSocket messages to relay as WS_DATA frames."""
                    while True:
                        message = await local_ws.receive_text()
                        await conn.send_ws_data(ws_id, message.encode("utf-8"))

                relay_task = asyncio.create_task(relay_to_local())
                local_task = asyncio.create_task(local_to_relay())

                try:
                    done, pending = await asyncio.wait(
                        {relay_task, local_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        if task.exception() is not None:
                            pass  # Suppress — stream errors are normal on disconnect
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass
                finally:
                    conn.remove_stream(ws_id)

    except Exception:
        pass
    finally:
        try:
            await conn.send_ws_close(ws_id)
        except Exception:
            pass
