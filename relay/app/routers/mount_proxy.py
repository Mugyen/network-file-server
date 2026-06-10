"""Mount proxy router — forwards browser HTTP requests through TunnelConnection."""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator
from urllib.parse import quote

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse


from relay.app.state import RelayState
from relay.app.exceptions import (
    AccessDeniedError,
    AuthenticationRequiredError,
    MountExpiredError,
    MountNotFoundError,
    MountOfflineError,
)
from relay.app.rate_limit import get_client_ip, limiter, proxy_request_rate
from relay.app.routers.landing import templates
from relay.app.services.access_policy import authorize, identity_from_cookies
from relay.app.services.html_rewriter import (
    HTML_REWRITE_MAX_BYTES,
    rewrite_html_body,
)
from tunnel.constants import FIRST_BYTE_TIMEOUT_S, MAX_PAYLOAD_BYTES
from tunnel.exceptions import (
    FirstByteTimeoutError,
    MetadataTooLargeError,
    TunnelSendError,
)
from tunnel.metadata import RequestMetadata, WsOpenMetadata
from tunnel.ws_payload import (
    WsMessageKind,
    decode_ws_message,
    encode_binary_message,
    encode_text_message,
)

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

# HTML asset-path rewriting lives in relay/app/services/html_rewriter.py.


@router.get("/m/{code}/status")
async def mount_status(request: Request, code: str) -> dict[str, str]:
    """Return the current status of a mount code.

    Returns JSON: {"status": "online"|"offline"|"expired"|"not_found"}
    Not rate-limited — status polling at 30s intervals should not consume
    the proxy rate limit budget.
    """
    state: RelayState = request.app.state.relay
    registry = state.require_registry()
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
@limiter.limit(proxy_request_rate)
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

    # Local ASGI mounts (e.g. the drop box) are forwarded in-process.
    state: RelayState = request.app.state.relay
    local = state.local_mounts.get(code)
    if local is not None:
        resp = await local.forward_request(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            content=await request.body(),
            query=str(request.url.query),
        )
        resp_content_type = resp.headers.get("content-type", "application/octet-stream")
        # Apply same HTML rewriting as tunnel-proxied responses (hardened:
        # passthrough on oversize/undecodable bodies).
        if resp_content_type.startswith("text/html"):
            rewritten_body = rewrite_html_body(
                resp.content, resp_content_type, f"/m/{code}"
            )
            return Response(
                content=rewritten_body,
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

    # --- Account access enforcement (allowlisted users bypass the server
    # password; non-allowlisted users fall back to it on RESTRICTED+pw
    # mounts; RESTRICTED+no-pw mounts require login/allowlist). ---
    registry = state.require_registry()
    identity = identity_from_cookies(request.cookies, state.session)
    try:
        decision = await authorize(registry, state.account_store, code, identity)
    except AuthenticationRequiredError:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        if "text/html" in request.headers.get("accept", ""):
            return RedirectResponse(
                url=f"/login?next={quote(next_url, safe='')}", status_code=302
            )
        return JSONResponse(
            {"error": "authentication required"}, status_code=401
        )
    except AccessDeniedError:
        return templates.TemplateResponse(
            request, "forbidden.html", status_code=403
        )

    # Extract client IP — reuses shared get_client_ip for consistency with rate limiter
    try:
        client_ip: str = get_client_ip(request)
    except ValueError:
        client_ip = "unknown"

    try:
        conn = await registry.get_connection(code)
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

    # Build forwarded headers — strip hop-by-hop + any spoofed X-WFS-*,
    # rewrite Host, then inject trusted identity for allowlisted users.
    forward_headers: dict[str, str] = {}
    for header_name, header_value in request.headers.items():
        lname = header_name.lower()
        if lname in HOP_BY_HOP or lname == "host" or lname.startswith("x-wfs-"):
            continue
        forward_headers[header_name] = header_value
    forward_headers["host"] = request.headers.get("host", "")
    if decision.identified:
        forward_headers["x-wfs-user"] = decision.username
        forward_headers["x-wfs-role"] = decision.role.value
        forward_headers["x-wfs-auth-bypass"] = "1"

    content_length: int = int(request.headers.get("content-length", "0"))

    metadata = RequestMetadata(
        method=request.method,
        path=f"/{path}",
        query=str(request.url.query),
        headers=forward_headers,
        content_length=content_length,
    )

    request_id = uuid.uuid4()
    conn.open_stream(request_id)
    try:
        await conn.send_open(request_id, metadata)

        # Stream request body as DATA frames so frames never exceed
        # MAX_PAYLOAD_BYTES. A zero-length DATA frame is the end-of-body
        # sentinel.
        async for chunk in request.stream():
            offset = 0
            while offset < len(chunk):
                end = offset + MAX_PAYLOAD_BYTES
                await conn.send_data(request_id, chunk[offset:end])
                offset = end
        await conn.send_data(request_id, b"")
    except MetadataTooLargeError:
        # Pathological header set from the browser — reject, do not crash.
        return Response("Request Header Fields Too Large", status_code=431)
    except TunnelSendError:
        # Socket went stale between lookup and send — clean 503, and the
        # heartbeat/receive loop will mark the mount offline shortly.
        logger.warning("Send failed mid-proxy: code=%s path=/%s", code, path)
        return Response("Mount connection lost", status_code=503)

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

    # For HTML responses, buffer the body (up to HTML_REWRITE_MAX_BYTES) and
    # rewrite absolute asset paths so /assets/... becomes /m/{code}/assets/...
    # in the browser. Oversized or undecodable bodies pass through unchanged
    # (see html_rewriter) — the rewrite is cosmetic, the proxy must not die.
    if resp_content_type.startswith("text/html"):
        body_parts: list[bytes] = []
        buffered = 0
        over_cap = False
        body_iter = conn.read_stream_iter(request_id)
        async for chunk in body_iter:
            body_parts.append(chunk)
            buffered += len(chunk)
            if buffered > HTML_REWRITE_MAX_BYTES:
                over_cap = True
                break

        duration_ms = round((time.monotonic() - start) * 1000)
        logger.info(
            "%s /%s -> %d %dms client=%s",
            request.method, path, resp_status, duration_ms, client_ip,
        )

        if not over_cap:
            # Drop content-length since rewriting changes the body size;
            # Response sets the correct value from the actual content.
            resp_headers.pop("content-length", None)
            rewritten = rewrite_html_body(
                b"".join(body_parts), resp_content_type, f"/m/{code}"
            )
            return Response(
                content=rewritten,
                status_code=resp_status,
                headers=resp_headers,
                media_type=resp_content_type,
            )

        async def passthrough_generator() -> AsyncGenerator[bytes, None]:
            """Stream the buffered prefix plus the remainder, unrewritten."""
            for part in body_parts:
                yield part
            async for chunk in body_iter:
                if await request.is_disconnected():
                    await conn.send_cancel(request_id)
                    return
                yield chunk

        logger.info(
            "HTML body exceeds rewrite cap (%d bytes buffered) — streaming "
            "unrewritten: code=%s path=/%s",
            buffered, code, path,
        )
        return StreamingResponse(
            passthrough_generator(),
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
    # Local ASGI mounts (e.g. the drop box) bridge in-process.
    state: RelayState = websocket.app.state.relay
    local = state.local_mounts.get(code)
    if local is not None:
        await websocket.accept()
        forward_headers = {
            k: v for k, v in websocket.headers.items()
            if k.lower() not in HOP_BY_HOP and k.lower() != "host"
        }
        await local.bridge_websocket(
            websocket,
            path,
            str(websocket.url.query) if websocket.url.query else "",
            forward_headers,
        )
        return

    registry = state.require_registry()
    identity = identity_from_cookies(websocket.cookies, state.session)
    try:
        decision = await authorize(registry, state.account_store, code, identity)
    except (AuthenticationRequiredError, AccessDeniedError):
        await websocket.accept()
        await websocket.close(code=1008)
        return

    try:
        conn = await registry.get_connection(code)
    except (MountNotFoundError, MountOfflineError, MountExpiredError):
        await websocket.accept()
        await websocket.close(code=1011)
        return

    await websocket.accept()

    # Forward non-hop-by-hop headers (including cookies); strip spoofed
    # X-WFS-* and inject trusted identity for allowlisted users.
    forward_headers: dict[str, str] = {}
    for header_name, header_value in websocket.headers.items():
        lname = header_name.lower()
        if lname in HOP_BY_HOP or lname == "host" or lname.startswith("x-wfs-"):
            continue
        forward_headers[header_name] = header_value
    forward_headers["host"] = websocket.headers.get("host", "")
    if decision.identified:
        forward_headers["x-wfs-user"] = decision.username
        forward_headers["x-wfs-role"] = decision.role.value
        forward_headers["x-wfs-auth-bypass"] = "1"

    ws_id = uuid.uuid4()
    conn.open_stream(ws_id)
    try:
        await conn.send_ws_open(
            ws_id,
            WsOpenMetadata(
                path=f"/{path}",
                query=str(websocket.url.query),
                headers=forward_headers,
            ),
        )
    except (MetadataTooLargeError, TunnelSendError) as exc:
        # Cannot reach the agent (oversized headers or stale socket) —
        # close the browser socket cleanly instead of crashing the bridge.
        logger.warning("WS open failed: code=%s path=/%s error=%s", code, path, exc)
        await websocket.close(code=1011)
        return

    async def browser_to_agent() -> None:
        """Forward browser messages (text or binary) to agent as WS_DATA frames."""
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            text = message.get("text")
            if text is not None:
                await conn.send_ws_data(ws_id, encode_text_message(text))
                continue
            data = message.get("bytes")
            if data is not None:
                await conn.send_ws_data(ws_id, encode_binary_message(data))

    async def agent_to_browser() -> None:
        """Forward WS_DATA frames from agent to browser, mirroring frame kind."""
        async for chunk in conn.read_stream_iter(ws_id):
            kind, data = decode_ws_message(chunk)
            if kind is WsMessageKind.TEXT:
                await websocket.send_text(data.decode("utf-8"))
            else:
                await websocket.send_bytes(data)

    browser_task = asyncio.create_task(browser_to_agent())
    agent_task = asyncio.create_task(agent_to_browser())

    try:
        done, pending = await asyncio.wait(
            {browser_task, agent_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            exc = task.exception()
            if exc is not None:
                logger.debug(
                    "Mount WS bridge task ended with error: code=%s ws_id=%s error=%r",
                    code,
                    ws_id,
                    exc,
                )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected — we just cancelled it.
            except Exception:
                logger.exception(
                    "Mount WS bridge task raised during cancellation: code=%s ws_id=%s",
                    code,
                    ws_id,
                )
    finally:
        try:
            await conn.send_ws_close(ws_id)
        except Exception as exc:
            # The agent tunnel may already be gone; nothing left to close.
            logger.debug(
                "Could not send WS_CLOSE to agent (tunnel already down?): code=%s ws_id=%s error=%r",
                code,
                ws_id,
                exc,
            )
