"""Tests for the mount proxy router and agent WebSocket endpoint."""

import asyncio
import json
import time
import uuid

import httpx
import pytest

from relay.app.routers.mount_proxy import rewrite_html_asset_paths
from relay.app.services.mount_registry import MountRegistry, get_registry, set_registry
from relay.app.enums import MountStatus
from tunnel.enums import FrameType


pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# rewrite_html_asset_paths unit tests
# ---------------------------------------------------------------------------


class TestRewriteHtmlAssetPaths:
    """Unit tests for HTML asset path rewriting in mount proxy."""

    def test_rewrites_script_src(self) -> None:
        html = '<script src="/assets/index-abc.js"></script>'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<script src="/m/CODE1/assets/index-abc.js"></script>'

    def test_rewrites_link_href(self) -> None:
        html = '<link rel="stylesheet" href="/assets/index-xyz.css">'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<link rel="stylesheet" href="/m/CODE1/assets/index-xyz.css">'

    def test_rewrites_favicon(self) -> None:
        html = '<link rel="icon" href="/favicon.ico">'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<link rel="icon" href="/m/CODE1/favicon.ico">'

    def test_does_not_double_rewrite(self) -> None:
        """Paths already containing /m/ prefix are not rewritten."""
        html = '<script src="/m/CODE1/assets/index.js"></script>'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == html

    def test_rewrites_single_quoted_attributes(self) -> None:
        html = "<script src='/assets/app.js'></script>"
        result = rewrite_html_asset_paths(html, "/m/XYZ")
        assert result == "<script src='/m/XYZ/assets/app.js'></script>"

    def test_full_index_html(self) -> None:
        """Full realistic index.html is rewritten correctly."""
        html = (
            '<!doctype html><html><head>'
            '<script type="module" src="/assets/index-C4XEGJkC.js"></script>'
            '<link rel="stylesheet" href="/assets/index-BZCOt5Ge.css">'
            '</head><body><div id="root"></div></body></html>'
        )
        result = rewrite_html_asset_paths(html, "/m/t7F5Twps")
        assert '"/m/t7F5Twps/assets/index-C4XEGJkC.js"' in result
        assert '"/m/t7F5Twps/assets/index-BZCOt5Ge.css"' in result

    def test_preserves_non_asset_content(self) -> None:
        """Non src/href content with slashes is not rewritten."""
        html = '<div data-path="/some/thing">text</div>'
        result = rewrite_html_asset_paths(html, "/m/CODE")
        assert result == html


async def test_proxy_get(registered_relay_client):
    """GET /m/{code}/some/path proxies to agent and returns 200 with body."""
    client_cm, registry = registered_relay_client
    async with client_cm as client:
        response = await client.get("/m/testcode/some/path")

    assert response.status_code == 200
    assert response.text == "hello world"


async def test_proxy_send_open_metadata(registered_relay_client):
    """send_open is called with correct method and path in metadata."""
    client_cm, registry = registered_relay_client
    # Grab the connection from the registry to inspect it later
    conn = registry.get_connection("testcode")

    async with client_cm as client:
        await client.get("/m/testcode/some/path")

    assert len(conn.sent_opens) == 1
    _request_id, metadata = conn.sent_opens[0]
    assert metadata["method"] == "GET"
    assert metadata["path"] == "/some/path"


async def test_proxy_post_body(registered_relay_client):
    """POST /m/{code}/upload streams request body as DATA frames, not in OPEN metadata."""
    client_cm, registry = registered_relay_client
    conn = registry.get_connection("testcode")

    async with client_cm as client:
        await client.post("/m/testcode/upload", content=b"hello")

    assert len(conn.sent_opens) == 1
    _request_id, metadata = conn.sent_opens[0]
    assert metadata["method"] == "POST"
    assert metadata["path"] == "/upload"
    # Body must NOT be embedded in OPEN metadata
    assert "body" not in metadata
    # Body must arrive as DATA frames followed by zero-length sentinel
    payloads = [payload for (_rid, payload) in conn.sent_data]
    assert len(payloads) >= 2, "Expected at least one body chunk and one sentinel"
    assert payloads[-1] == b"", "Last DATA frame must be zero-length sentinel"
    assert b"".join(payloads[:-1]) == b"hello"


async def test_proxy_large_upload_streams_body(relay_app):
    """POST with body >64KB sends body as multiple DATA frames, not in OPEN metadata."""
    from tests.relay.conftest import MockTunnelConnection
    from relay.app.services.mount_registry import get_registry
    from tunnel.constants import MAX_PAYLOAD_BYTES

    conn = MockTunnelConnection()
    registry = get_registry()
    registry.register("largecode", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    # Build a body larger than one frame (65536 bytes)
    large_body = b"X" * (MAX_PAYLOAD_BYTES + 1024)

    transport = httpx.ASGITransport(app=relay_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/m/largecode/upload", content=large_body)

    assert len(conn.sent_opens) == 1
    _request_id, metadata = conn.sent_opens[0]
    # Body must NOT be in OPEN metadata
    assert "body" not in metadata
    # Must have multiple DATA frames
    payloads = [payload for (_rid, payload) in conn.sent_data]
    assert len(payloads) >= 3, "Expected multiple body chunks plus sentinel for large body"
    # Each non-sentinel chunk must be within frame size limit
    for chunk in payloads[:-1]:
        assert len(chunk) <= MAX_PAYLOAD_BYTES, f"Chunk size {len(chunk)} exceeds MAX_PAYLOAD_BYTES"
    # Last frame must be zero-length sentinel
    assert payloads[-1] == b""
    # Reconstructed body must match original
    assert b"".join(payloads[:-1]) == large_body


async def test_proxy_get_no_body_sends_sentinel(registered_relay_client):
    """GET request sends zero-length DATA sentinel immediately after OPEN (no body)."""
    client_cm, registry = registered_relay_client
    conn = registry.get_connection("testcode")

    async with client_cm as client:
        await client.get("/m/testcode/some/path")

    assert len(conn.sent_opens) == 1
    _request_id, metadata = conn.sent_opens[0]
    assert metadata["method"] == "GET"
    # GET has no body — only the zero-length sentinel DATA frame
    payloads = [payload for (_rid, payload) in conn.sent_data]
    assert payloads == [b""], "GET must send exactly the zero-length sentinel DATA frame"


async def test_proxy_not_found(relay_client):
    """GET /m/unknown/path returns 404 with not_found template HTML."""
    response = await relay_client.get("/m/unknown/path")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    body = response.text.lower()
    assert "not found" in body or "mount" in body


async def test_not_found_has_code_input(relay_client):
    """not_found response HTML contains a code input for retry."""
    response = await relay_client.get("/m/unknown/path")
    assert response.status_code == 404
    body = response.text
    assert '<input' in body
    assert 'name="code"' in body


async def test_proxy_offline(registered_relay_client):
    """After mark_offline, proxy returns 503 with offline template."""
    client_cm, registry = registered_relay_client
    registry.mark_offline("testcode")

    async with client_cm as client:
        response = await client.get("/m/testcode/path")

    assert response.status_code == 503
    body = response.text.lower()
    assert "offline" in body


async def test_proxy_expired_page(relay_app):
    """Mount with EXPIRED status returns 410 with expired template."""
    from tests.relay.conftest import MockTunnelConnection
    from relay.app.services.mount_registry import get_registry

    conn = MockTunnelConnection()
    registry = get_registry()
    registry.register("expiredcode", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)
    # Force EXPIRED status directly on the record
    registry._mounts["expiredcode"].status = MountStatus.EXPIRED

    import httpx
    transport = httpx.ASGITransport(app=relay_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/m/expiredcode/path")

    assert response.status_code == 410
    body = response.text.lower()
    assert "expired" in body


async def test_proxy_rewrites_html_asset_paths(relay_app):
    """HTML responses have absolute asset paths rewritten with mount prefix."""
    from tests.relay.conftest import MockTunnelConnection
    from relay.app.services.mount_registry import get_registry

    html_body = (
        '<html><head>'
        '<script src="/assets/index-abc.js"></script>'
        '<link href="/assets/index-xyz.css">'
        '</head></html>'
    )
    conn = MockTunnelConnection()
    conn.first_chunk = json.dumps(
        {"status": 200, "headers": {"content-type": "text/html; charset=utf-8"}}
    ).encode()
    conn.body_chunks = [html_body.encode("utf-8")]

    registry = get_registry()
    registry.register("htmlcode", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    transport = httpx.ASGITransport(app=relay_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/m/htmlcode/")

    assert response.status_code == 200
    assert '"/m/htmlcode/assets/index-abc.js"' in response.text
    assert '"/m/htmlcode/assets/index-xyz.css"' in response.text


async def test_proxy_does_not_rewrite_non_html(registered_relay_client):
    """Non-HTML responses (e.g. JSON) are streamed without rewriting."""
    client_cm, registry = registered_relay_client
    conn = registry.get_connection("testcode")
    conn.first_chunk = json.dumps(
        {"status": 200, "headers": {"content-type": "application/json"}}
    ).encode()
    conn.body_chunks = [b'{"path": "/assets/test"}']

    async with client_cm as client:
        response = await client.get("/m/testcode/api/info")

    assert response.status_code == 200
    assert response.text == '{"path": "/assets/test"}'


async def test_proxy_strips_hop_by_hop_headers(registered_relay_client):
    """Hop-by-hop headers are not forwarded in OPEN frame metadata headers."""
    client_cm, registry = registered_relay_client
    conn = registry.get_connection("testcode")

    async with client_cm as client:
        await client.get(
            "/m/testcode/path",
            headers={
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
                "X-Custom-Header": "keep-me",
            },
        )

    assert len(conn.sent_opens) == 1
    _request_id, metadata = conn.sent_opens[0]
    fwd_headers = {k.lower(): v for k, v in metadata["headers"].items()}
    assert "connection" not in fwd_headers
    assert "transfer-encoding" not in fwd_headers


async def test_proxy_first_byte_timeout(relay_app):
    """When read_stream raises FirstByteTimeoutError, proxy returns 504."""
    from tests.relay.conftest import MockTunnelConnection
    from tunnel.exceptions import FirstByteTimeoutError
    from relay.app.services.mount_registry import get_registry

    class TimeoutMockConnection(MockTunnelConnection):
        async def read_stream(self, request_id, timeout_s: float) -> bytes:
            raise FirstByteTimeoutError("timed out")

    conn = TimeoutMockConnection()
    registry = get_registry()
    registry.register("timeoutcode", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    import httpx
    transport = httpx.ASGITransport(app=relay_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/m/timeoutcode/path")

    assert response.status_code == 504


# ---------------------------------------------------------------------------
# WebSocket proxy endpoint tests
# ---------------------------------------------------------------------------


class MockWSConnection:
    """MockTunnelConnection extended to support WS send methods and tracking."""

    def __init__(self) -> None:
        self.opened_streams: list = []
        self.sent_ws_opens: list[tuple] = []   # (ws_id, metadata)
        self.sent_ws_data: list[tuple] = []     # (ws_id, payload)
        self.sent_ws_closes: list = []          # ws_id
        # Queue for agent_to_browser messages (chunks to yield from read_stream_iter)
        self._ws_response_queue: asyncio.Queue = asyncio.Queue()

    def open_stream(self, request_id: uuid.UUID) -> None:
        self.opened_streams.append(request_id)

    async def send_ws_open(self, ws_id: uuid.UUID, metadata: dict) -> None:
        self.sent_ws_opens.append((ws_id, metadata))

    async def send_ws_data(self, ws_id: uuid.UUID, payload: bytes) -> None:
        self.sent_ws_data.append((ws_id, payload))

    async def send_ws_close(self, ws_id: uuid.UUID) -> None:
        self.sent_ws_closes.append(ws_id)

    async def read_stream_iter(self, ws_id: uuid.UUID):
        # Block indefinitely until a message is put in the queue or the queue is closed
        # Yields each chunk from the queue; None sentinel stops the iteration
        while True:
            chunk = await self._ws_response_queue.get()
            if chunk is None:
                return
            yield chunk

    def push_response_chunk(self, chunk: bytes) -> None:
        """Push a chunk for agent_to_browser forwarding."""
        self._ws_response_queue.put_nowait(chunk)

    def stop_response_stream(self) -> None:
        """Signal read_stream_iter to stop by pushing None sentinel."""
        self._ws_response_queue.put_nowait(None)


async def test_proxy_websocket_accepts_upgrade(relay_app):
    """Browser WebSocket upgrade to /m/{code}/ws is accepted (not rejected 4xx)."""
    from httpx_ws import aconnect_ws
    from httpx_ws.transport import ASGIWebSocketTransport

    conn = MockWSConnection()
    registry = get_registry()
    registry.register("wscode", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    async with ASGIWebSocketTransport(app=relay_app) as transport:
        async with aconnect_ws("ws://test/m/wscode/ws", httpx.AsyncClient(transport=transport)) as ws:
            # Connection opened successfully — just close it
            pass


async def test_proxy_websocket_sends_ws_open_frame(relay_app):
    """Relay sends WS_OPEN frame to agent with path and query metadata."""
    from httpx_ws import aconnect_ws
    from httpx_ws.transport import ASGIWebSocketTransport

    conn = MockWSConnection()
    registry = get_registry()
    registry.register("wscode2", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    async with ASGIWebSocketTransport(app=relay_app) as transport:
        async with aconnect_ws("ws://test/m/wscode2/ws?foo=bar", httpx.AsyncClient(transport=transport)) as ws:
            pass

    assert len(conn.sent_ws_opens) == 1
    _ws_id, metadata = conn.sent_ws_opens[0]
    assert metadata["path"] == "/ws"
    assert "foo=bar" in metadata["query"]


async def test_proxy_websocket_sends_ws_close_on_disconnect(relay_app):
    """Relay sends WS_CLOSE to agent when browser disconnects."""
    from httpx_ws import aconnect_ws
    from httpx_ws.transport import ASGIWebSocketTransport

    conn = MockWSConnection()
    registry = get_registry()
    registry.register("wscode3", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    async with ASGIWebSocketTransport(app=relay_app) as transport:
        async with aconnect_ws("ws://test/m/wscode3/ws", httpx.AsyncClient(transport=transport)) as ws:
            pass

    assert len(conn.sent_ws_closes) == 1


async def test_proxy_websocket_forwards_browser_text_to_agent(relay_app):
    """Browser text messages are forwarded to agent as WS_DATA."""
    from httpx_ws import aconnect_ws
    from httpx_ws.transport import ASGIWebSocketTransport

    conn = MockWSConnection()
    registry = get_registry()
    registry.register("wscode4", conn, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    async with ASGIWebSocketTransport(app=relay_app) as transport:
        async with aconnect_ws("ws://test/m/wscode4/ws", httpx.AsyncClient(transport=transport)) as ws:
            await ws.send_text("hello from browser")
            # Allow relay browser_to_agent task to process the message before disconnect
            await asyncio.sleep(0.05)

    # The send_ws_data should have been called with the message
    payloads = [payload for (_ws_id, payload) in conn.sent_ws_data]
    assert b"hello from browser" in payloads


async def test_proxy_websocket_not_found_accepts_then_closes(relay_app):
    """WebSocket to unknown mount code is accepted (no 403) then closed."""
    from httpx_ws import aconnect_ws
    from httpx_ws.transport import ASGIWebSocketTransport

    async with ASGIWebSocketTransport(app=relay_app) as transport:
        # Must not raise WebSocketUpgradeError — server accepts before closing
        async with aconnect_ws("ws://test/m/unknown_ws_code/ws", httpx.AsyncClient(transport=transport)):
            pass
