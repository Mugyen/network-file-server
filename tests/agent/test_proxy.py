"""Tests for agent proxy — OPEN frame handler with ASGI dispatch and response streaming."""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import httpx_ws
import pytest
from fastapi import FastAPI, WebSocket
from fastapi.responses import Response, StreamingResponse
from httpx import ASGITransport
from httpx_ws.transport import ASGIWebSocketTransport

from tunnel.connection import StreamState
from tunnel.exceptions import StreamNotFoundError


def make_test_app_with_body(body: bytes, status_code: int = 200) -> FastAPI:
    """Create a minimal FastAPI app that returns a fixed body and status code."""
    test_app = FastAPI()

    @test_app.get("/hello")
    async def get_hello() -> Response:
        return Response(content=body, status_code=status_code)

    return test_app


def make_streaming_app(chunk_size: int, num_chunks: int) -> FastAPI:
    """Create a FastAPI app that streams chunks of fixed size."""
    test_app = FastAPI()
    chunk = b"x" * chunk_size

    async def generate():
        for _ in range(num_chunks):
            yield chunk

    @test_app.get("/stream")
    async def get_stream() -> StreamingResponse:
        return StreamingResponse(generate(), media_type="application/octet-stream")

    return test_app


def make_conn_mock(request_body: bytes = b"") -> MagicMock:
    """Return a mock TunnelConnection with async send_data and send_close.

    Pre-loads the StreamState queue with request_body chunks and a zero-length
    sentinel so handle_open_frame can reconstruct the body correctly.

    Args:
        request_body: The request body bytes to pre-load into the stream queue.
    """
    conn = MagicMock()
    conn.send_data = AsyncMock()
    conn.send_close = AsyncMock()
    conn.remove_stream = MagicMock()

    # Build a real StreamState so queue.get() works correctly.
    state = StreamState()
    if request_body:
        state.queue.put_nowait(request_body)
    # Zero-length sentinel signals end-of-body to handle_open_frame.
    state.queue.put_nowait(b"")

    conn.get_stream = MagicMock(return_value=state)
    return conn


@pytest.mark.asyncio
async def test_handle_open_frame_sends_metadata_then_body_then_close() -> None:
    """Test 1: handle_open_frame sends response metadata as first DATA frame, body as subsequent DATA frames, then CLOSE."""
    from agent.proxy import handle_open_frame

    body = b"hello world"
    test_app = make_test_app_with_body(body, status_code=200)
    asgi_client = httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://local")
    conn = make_conn_mock()
    request_id = uuid.uuid4()

    metadata = {
        "method": "GET",
        "path": "/hello",
        "query": "",
        "headers": {},
        "body": "",
    }

    await handle_open_frame(conn, request_id, metadata, asgi_client)

    # First DATA call should be JSON metadata with status + headers
    assert conn.send_data.call_count >= 1
    first_call_payload = conn.send_data.call_args_list[0][0][1]
    first_frame = json.loads(first_call_payload.decode("utf-8"))
    assert first_frame["status"] == 200
    assert "headers" in first_frame

    # CLOSE must be sent exactly once
    conn.send_close.assert_called_once_with(request_id)

    # send_data must have been called for the body chunk too
    assert conn.send_data.call_count >= 2


@pytest.mark.asyncio
async def test_handle_open_frame_streams_in_64k_chunks() -> None:
    """Test 2: Response body is streamed in 65536-byte chunks."""
    from agent.proxy import handle_open_frame

    # Build a body larger than 65536 to force multiple chunks
    chunk_size = 65536
    body = b"y" * (chunk_size + 1)  # 65537 bytes -> 2 body chunks
    test_app = make_test_app_with_body(body, status_code=200)
    asgi_client = httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://local")
    conn = make_conn_mock()
    request_id = uuid.uuid4()

    metadata = {
        "method": "GET",
        "path": "/hello",
        "query": "",
        "headers": {},
        "body": "",
    }

    await handle_open_frame(conn, request_id, metadata, asgi_client)

    # call_count: 1 (metadata) + at least 2 (body chunks)
    assert conn.send_data.call_count >= 3
    # Last data call before close should be the second body chunk (1 byte)
    body_calls = conn.send_data.call_args_list[1:]  # skip metadata frame
    total_body = b"".join(c[0][1] for c in body_calls)
    assert total_body == body


@pytest.mark.asyncio
async def test_handle_open_frame_cancel_via_stream_not_found_exits_cleanly() -> None:
    """Test 3: When StreamNotFoundError is raised on send_data (CANCEL received), handler exits without raising."""
    from agent.proxy import handle_open_frame

    body = b"some body content"
    test_app = make_test_app_with_body(body, status_code=200)
    asgi_client = httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://local")

    conn = make_conn_mock()
    request_id = uuid.uuid4()
    # Make send_data raise StreamNotFoundError on first call (metadata frame)
    conn.send_data.side_effect = StreamNotFoundError("stream cancelled")

    metadata = {
        "method": "GET",
        "path": "/hello",
        "query": "",
        "headers": {},
        "body": "",
    }

    # Should NOT raise
    await handle_open_frame(conn, request_id, metadata, asgi_client)

    # send_data called once (failed), send_close NOT called (cancelled)
    assert conn.send_data.call_count == 1
    conn.send_close.assert_not_called()


@pytest.mark.asyncio
async def test_handle_open_frame_calls_print_request_line() -> None:
    """Test 4: print_request_line is called with method, path, and status after response completes."""
    from agent.proxy import handle_open_frame

    body = b"ok"
    test_app = make_test_app_with_body(body, status_code=201)
    asgi_client = httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://local")
    conn = make_conn_mock()
    request_id = uuid.uuid4()

    metadata = {
        "method": "GET",
        "path": "/hello",
        "query": "",
        "headers": {},
        "body": "",
    }

    with patch("agent.proxy.print_request_line") as mock_print:
        await handle_open_frame(conn, request_id, metadata, asgi_client)
        mock_print.assert_called_once_with("GET", "/hello", 201)


@pytest.mark.asyncio
async def test_handle_open_frame_concurrent_dispatch() -> None:
    """Test 5: Concurrent OPEN frames are handled independently — both complete."""
    from agent.proxy import handle_open_frame

    body_a = b"response A"
    body_b = b"response B"

    app_a = make_test_app_with_body(body_a, status_code=200)
    app_b = make_test_app_with_body(body_b, status_code=200)

    client_a = httpx.AsyncClient(transport=ASGITransport(app=app_a), base_url="http://local")
    client_b = httpx.AsyncClient(transport=ASGITransport(app=app_b), base_url="http://local")

    conn_a = make_conn_mock()
    conn_b = make_conn_mock()

    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()

    metadata = {
        "method": "GET",
        "path": "/hello",
        "query": "",
        "headers": {},
        "body": "",
    }

    task_a = asyncio.create_task(handle_open_frame(conn_a, rid_a, metadata, client_a))
    task_b = asyncio.create_task(handle_open_frame(conn_b, rid_b, metadata, client_b))

    await asyncio.gather(task_a, task_b)

    # Both should have completed: send_data called + send_close called
    conn_a.send_close.assert_called_once_with(rid_a)
    conn_b.send_close.assert_called_once_with(rid_b)


@pytest.mark.asyncio
async def test_handle_open_frame_with_query_string() -> None:
    """Test that query string is appended to URL correctly."""
    from agent.proxy import handle_open_frame

    test_app = FastAPI()

    @test_app.get("/search")
    async def search(q: str = "") -> Response:
        return Response(content=q.encode(), status_code=200)

    asgi_client = httpx.AsyncClient(transport=ASGITransport(app=test_app), base_url="http://local")
    conn = make_conn_mock()
    request_id = uuid.uuid4()

    metadata = {
        "method": "GET",
        "path": "/search",
        "query": "q=hello",
        "headers": {},
        "body": "",
    }

    await handle_open_frame(conn, request_id, metadata, asgi_client)

    # Should succeed and send CLOSE
    conn.send_close.assert_called_once_with(request_id)
    # Second DATA call should contain "hello"
    body_calls = conn.send_data.call_args_list[1:]
    total_body = b"".join(c[0][1] for c in body_calls)
    assert b"hello" in total_body


# ---------------------------------------------------------------------------
# handle_ws_open_frame tests
# ---------------------------------------------------------------------------


def make_ws_test_app() -> FastAPI:
    """Create a minimal FastAPI app with a /ws WebSocket endpoint for testing."""
    ws_app = FastAPI()
    received_messages: list[str] = []

    @ws_app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        async for message in websocket.iter_text():
            received_messages.append(message)
            await websocket.send_text(f"echo:{message}")

    ws_app.state.received_messages = received_messages
    return ws_app


def make_ws_conn_mock() -> MagicMock:
    """Return a mock TunnelConnection with WS send methods and read_stream_iter via queue."""
    conn = MagicMock()
    conn.send_ws_data = AsyncMock()
    conn.send_ws_close = AsyncMock()
    conn._relay_to_local_queue: asyncio.Queue = asyncio.Queue()

    async def _read_stream_iter(ws_id: uuid.UUID):
        while True:
            chunk = await conn._relay_to_local_queue.get()
            if chunk is None:
                return
            yield chunk

    conn.read_stream_iter = _read_stream_iter
    return conn


@pytest.mark.asyncio
async def test_handle_ws_open_frame_bridges_local_ws_messages_to_relay() -> None:
    """handle_ws_open_frame opens local WS and bridges outbound messages to relay."""
    from agent.proxy import handle_ws_open_frame

    ws_app = make_ws_test_app()
    conn = make_ws_conn_mock()
    ws_id = uuid.uuid4()
    metadata = {"path": "/ws", "query": ""}

    task = asyncio.create_task(
        handle_ws_open_frame(conn, ws_id, metadata, ws_app)
    )

    # Give the handler time to connect and set up the WS
    await asyncio.sleep(0.05)

    # Push a message from relay to local WS (relay_to_local direction)
    await conn._relay_to_local_queue.put(b"hello from relay")
    await asyncio.sleep(0.05)

    # The local WS echo handler should have sent "echo:hello from relay"
    # which handle_ws_open_frame should forward via send_ws_data
    # Close the stream to terminate
    await conn._relay_to_local_queue.put(None)
    await asyncio.sleep(0.05)

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    # send_ws_data should have been called with the echo response
    assert conn.send_ws_data.call_count >= 1
    all_payloads = [call[0][1] for call in conn.send_ws_data.call_args_list]
    assert any(b"echo:hello from relay" in p for p in all_payloads)


@pytest.mark.asyncio
async def test_handle_ws_open_frame_sends_ws_close_on_finish() -> None:
    """handle_ws_open_frame sends WS_CLOSE to relay when local WS closes."""
    from agent.proxy import handle_ws_open_frame

    ws_app = make_ws_test_app()
    conn = make_ws_conn_mock()
    ws_id = uuid.uuid4()
    metadata = {"path": "/ws", "query": ""}

    task = asyncio.create_task(
        handle_ws_open_frame(conn, ws_id, metadata, ws_app)
    )

    # Give the handler time to connect
    await asyncio.sleep(0.05)

    # Signal stream closure via None sentinel
    await conn._relay_to_local_queue.put(None)
    await asyncio.sleep(0.1)

    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    conn.send_ws_close.assert_called_once_with(ws_id)


@pytest.mark.asyncio
async def test_handle_ws_open_frame_uses_query_string() -> None:
    """handle_ws_open_frame appends query string to the WS URL."""
    from agent.proxy import handle_ws_open_frame

    query_received: list[str] = []

    ws_app = FastAPI()

    @ws_app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket, q: str = "") -> None:
        query_received.append(q)
        await websocket.accept()
        # Just close immediately
        await websocket.close()

    conn = make_ws_conn_mock()
    ws_id = uuid.uuid4()
    metadata = {"path": "/ws", "query": "q=testval"}

    # Run handler — it will connect to local WS which immediately closes
    task = asyncio.create_task(
        handle_ws_open_frame(conn, ws_id, metadata, ws_app)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass

    assert "testval" in query_received
