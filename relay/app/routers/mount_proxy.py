"""Mount proxy router — forwards browser HTTP requests through TunnelConnection."""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

import httpx
import httpx_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.config import get_config
from relay.app.exceptions import MountExpiredError, MountNotFoundError, MountOfflineError
from relay.app.rate_limit import get_client_ip, limiter
from relay.app.routers.landing import templates
from relay.app.services.dropbox import get_dropbox_app, get_dropbox_client
from relay.app.services.mount_registry import get_registry
from tunnel.constants import FIRST_BYTE_TIMEOUT_S, MAX_PAYLOAD_BYTES
from tunnel.exceptions import FirstByteTimeoutError

logger = logging.getLogger("relay.proxy")

router = APIRouter()

# Standard hop-by-hop headers that must not be forwarded to the agent.
# All lowercase for case-insensitive comparison.
HOP_BY_HOP: frozenset[str] = frozenset(
    {
        "connection",
        "keep-alive",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
    }
)

# Pattern matching src="/ or href="/ attribute values pointing to absolute paths.
# Captures the attribute prefix so we can rewrite only the path portion.
_ASSET_PATH_RE: re.Pattern[str] = re.compile(r'((?:src|href)=["\'])/(?!m/)')


def rewrite_html_asset_paths(html: str, mount_prefix: str) -> str:
    """Rewrite absolute asset paths in HTML to include the mount prefix.

    Transforms ``src="/assets/..."`` into ``src="/m/{code}/assets/..."`` (and
    likewise for ``href``). Only rewrites paths that don't already start with
    ``/m/`` to avoid double-rewriting.

    Args:
        html:         Raw HTML string from the agent response.
        mount_prefix: The mount URL prefix, e.g. ``/m/ABC123``.

    Returns:
        HTML string with asset paths rewritten to include the mount prefix.
    """
    return _ASSET_PATH_RE.sub(rf"\1{mount_prefix}/", html)


@router.get("/m/{code}/status")
async def mount_status(code: str) -> dict[str, str]:
    """Return the current status of a mount code.

    Returns JSON: {"status": "online"|"offline"|"expired"|"not_found"}
    Not rate-limited — status polling at 30s intervals should not consume
    the proxy rate limit budget.
    """
    registry = get_registry()
    try:
        await registry.get_connection(code)
        return {"status": "online"}
    except RuntimeError:
        # Local mount (e.g. drop box) — no tunnel connection but still online
        return {"status": "online"}
    except MountOfflineError:
        return {"status": "offline"}
    except MountExpiredError:
        return {"status": "expired"}
    except MountNotFoundError:
        return {"status": "not_found"}


@router.api_route(
    "/m/{code}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@limiter.limit(lambda: get_config().proxy_request_rate)
async def proxy_request(request: Request, code: str, path: str) -> Response:
    """Proxy a browser HTTP request through the tunnel to the registered agent.

    Looks up the TunnelConnection for `code`, builds OPEN frame metadata from
    the request, streams the agent response back to the browser as a
    StreamingResponse. Renders Jinja2 error pages for missing/offline/expired
    mounts.

    Args:
        request: The incoming FastAPI request from the browser.
        code:    Mount code extracted from the URL path.
        path:    Remaining path after the mount code.

    Returns:
        StreamingResponse on success, TemplateResponse on error states,
        or plain Response on timeout.
    """
    start: float = time.monotonic()

    # Drop box interception — forward to local server app via httpx ASGITransport
    dropbox_client = get_dropbox_client()
    config = get_config()
    if dropbox_client is not None and code == config.dropbox_code:
        resp = await dropbox_client.request(
            method=request.method,
            url=f"/{path}",
            headers=dict(request.headers),
            content=await request.body(),
            params=str(request.url.query) if request.url.query else None,
        )
        resp_content_type = resp.headers.get("content-type", "application/octet-stream")
        # Apply same HTML rewriting as tunnel-proxied responses
        if resp_content_type.startswith("text/html"):
            rewritten = rewrite_html_asset_paths(resp.text, f"/m/{code}")
            return Response(
                content=rewritten,
                status_code=resp.status_code,
                headers={k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "content-length"},
                media_type=resp_content_type,
            )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP},
            media_type=resp_content_type,
        )

    # Extract client IP — reuses shared get_client_ip for consistency with rate limiter
    try:
        client_ip: str = get_client_ip(request)
    except ValueError:
        client_ip = "unknown"

    try:
        conn = await get_registry().get_connection(code)
    except MountNotFoundError:
        return templates.TemplateResponse(
            request, "not_found.html", status_code=404
        )
    except MountOfflineError:
        return templates.TemplateResponse(
            request, "offline.html", status_code=503
        )
    except MountExpiredError:
        return templates.TemplateResponse(
            request, "expired.html", status_code=410
        )

    # Build forwarded headers — strip hop-by-hop, rewrite Host
    forward_headers: dict[str, str] = {}
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in HOP_BY_HOP and header_name.lower() != "host":
            forward_headers[header_name] = header_value
    forward_headers["host"] = request.headers.get("host", "")

    content_length: int = int(request.headers.get("content-length", "0"))

    metadata: dict = {
        "method": request.method,
        "path": f"/{path}",
        "query": str(request.url.query),
        "headers": forward_headers,
        "content_length": content_length,
    }

    request_id = uuid.uuid4()
    conn.open_stream(request_id)
    await conn.send_open(request_id, metadata)

    # Stream request body as DATA frames so frames never exceed MAX_PAYLOAD_BYTES.
    # A zero-length DATA frame acts as the end-of-body sentinel.
    async for chunk in request.stream():
        offset = 0
        while offset < len(chunk):
            end = offset + MAX_PAYLOAD_BYTES
            await conn.send_data(request_id, chunk[offset:end])
            offset = end
    await conn.send_data(request_id, b"")

    try:
        first_chunk = await conn.read_stream(request_id, FIRST_BYTE_TIMEOUT_S)
    except FirstByteTimeoutError:
        duration_ms: int = round((time.monotonic() - start) * 1000)
        logger.info(
            "%s /%s -> 504 %dms client=%s",
            request.method, path, duration_ms, client_ip,
        )
        return Response("Gateway Timeout", status_code=504)

    response_meta: dict = json.loads(first_chunk)
    resp_status: int = response_meta.get("status", 200)
    resp_headers_raw: dict = response_meta.get("headers", {})

    # Strip hop-by-hop headers from the agent's response headers
    resp_headers: dict[str, str] = {
        k: v
        for k, v in resp_headers_raw.items()
        if k.lower() not in HOP_BY_HOP
    }

    # Extract content-type separately so StreamingResponse can set media_type
    resp_content_type: str = resp_headers.pop("content-type", "application/octet-stream")

    # For HTML responses, buffer the full body and rewrite absolute asset paths
    # so that /assets/... becomes /m/{code}/assets/... in the browser.
    # Drop content-length since rewriting changes the body size; Response
    # will set the correct value from the actual content.
    if resp_content_type.startswith("text/html"):
        resp_headers.pop("content-length", None)
        body_parts: list[bytes] = []
        async for chunk in conn.read_stream_iter(request_id):
            body_parts.append(chunk)
        html_body = b"".join(body_parts).decode("utf-8")
        rewritten = rewrite_html_asset_paths(html_body, f"/m/{code}")
        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "%s /%s -> %d %dms client=%s",
            request.method, path, resp_status, duration_ms, client_ip,
        )
        return Response(
            content=rewritten,
            status_code=resp_status,
            headers=resp_headers,
            media_type=resp_content_type,
        )

    async def stream_generator() -> AsyncGenerator[bytes, None]:
        """Yield body chunks from the tunnel stream, cancelling on browser disconnect."""
        async for chunk in conn.read_stream_iter(request_id):
            if await request.is_disconnected():
                await conn.send_cancel(request_id)
                return
            yield chunk

    duration_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "%s /%s -> %d %dms client=%s",
        request.method, path, resp_status, duration_ms, client_ip,
    )
    return StreamingResponse(
        stream_generator(),
        status_code=resp_status,
        headers=resp_headers,
        media_type=resp_content_type,
    )


@router.websocket("/m/{code}/{path:path}")
async def proxy_websocket(websocket: WebSocket, code: str, path: str) -> None:
    """Proxy a browser WebSocket connection through the tunnel to the registered agent.

    Accepts the WebSocket upgrade, looks up the TunnelConnection for `code`,
    opens a stream, sends WS_OPEN to the agent, then bridges messages
    bidirectionally until either the browser or the agent disconnects.

    On missing/offline/expired mount, accepts the upgrade then immediately
    closes with code 1011 (internal error). Accepting first is required
    because Starlette sends HTTP 403 if close() is called before accept().

    Args:
        websocket: The incoming FastAPI WebSocket connection from the browser.
        code:      Mount code extracted from the URL path.
        path:      Remaining path after the mount code.
    """
    # Drop box WebSocket: bridge to local server app via ASGIWebSocketTransport
    if code == get_config().dropbox_code:
        app = get_dropbox_app()
        await websocket.accept()
        query = str(websocket.url.query) if websocket.url.query else ""
        local_ws_url = f"ws://dropbox/{path}"
        if query:
            local_ws_url = f"{local_ws_url}?{query}"
        forward_headers = {
            k: v for k, v in websocket.headers.items()
            if k.lower() not in HOP_BY_HOP and k.lower() != "host"
        }
        try:
            async with ASGIWebSocketTransport(app=app) as ws_transport:
                async with httpx_ws.aconnect_ws(
                    local_ws_url,
                    httpx.AsyncClient(transport=ws_transport),
                    headers=forward_headers,
                    keepalive_ping_interval_seconds=None,
                ) as local_ws:

                    async def browser_to_local() -> None:
                        """Forward text messages from browser to local drop box app."""
                        async for msg in websocket.iter_text():
                            await local_ws.send_text(msg)

                    async def local_to_browser() -> None:
                        """Forward messages from local drop box app to browser."""
                        while True:
                            msg = await local_ws.receive_text()
                            await websocket.send_text(msg)

                    b2l = asyncio.create_task(browser_to_local())
                    l2b = asyncio.create_task(local_to_browser())
                    try:
                        done, pending = await asyncio.wait(
                            {b2l, l2b}, return_when=asyncio.FIRST_COMPLETED,
                        )
                        for t in pending:
                            t.cancel()
                            try:
                                await t
                            except (asyncio.CancelledError, Exception):
                                pass
                    finally:
                        pass
        except Exception:
            pass
        return

    try:
        conn = await get_registry().get_connection(code)
    except (MountNotFoundError, MountOfflineError, MountExpiredError):
        await websocket.accept()
        await websocket.close(code=1011)
        return

    await websocket.accept()

    # Forward non-hop-by-hop headers (including cookies) to agent
    forward_headers: dict[str, str] = {}
    for header_name, header_value in websocket.headers.items():
        if header_name.lower() not in HOP_BY_HOP and header_name.lower() != "host":
            forward_headers[header_name] = header_value
    forward_headers["host"] = websocket.headers.get("host", "")

    ws_id = uuid.uuid4()
    conn.open_stream(ws_id)
    await conn.send_ws_open(
        ws_id,
        {
            "path": f"/{path}",
            "query": str(websocket.url.query),
            "headers": forward_headers,
        },
    )

    async def browser_to_agent() -> None:
        """Forward text messages from browser to agent as WS_DATA frames."""
        async for message in websocket.iter_text():
            await conn.send_ws_data(ws_id, message.encode("utf-8"))

    async def agent_to_browser() -> None:
        """Forward WS_DATA frames from agent to browser as text messages."""
        async for chunk in conn.read_stream_iter(ws_id):
            await websocket.send_text(chunk.decode("utf-8"))

    browser_task = asyncio.create_task(browser_to_agent())
    agent_task = asyncio.create_task(agent_to_browser())

    try:
        done, pending = await asyncio.wait(
            {browser_task, agent_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    finally:
        try:
            await conn.send_ws_close(ws_id)
        except Exception:
            pass
