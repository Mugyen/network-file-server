"""Tests for agent connection loop and reconnect behavior."""

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from tunnel.exceptions import StreamNotFoundError


def make_mock_conn(control_responses: list) -> MagicMock:
    """Create a mock TunnelConnection that returns control_responses in sequence."""
    conn = MagicMock()
    conn.receive_control = AsyncMock(side_effect=control_responses)
    conn.start_heartbeat = MagicMock()
    conn.close = AsyncMock()
    conn._ws = MagicMock()
    conn._ws.receive = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_connect_and_serve_receives_mount_registered(tmp_path: Path) -> None:
    """Test 1: connect_and_serve connects to relay, receives mount_registered, starts heartbeat."""
    from agent.connection import connect_and_serve

    assigned_code = "ABC12345"

    # Patch websockets.connect to return a mock WS
    mock_ws = MagicMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)

    # WebSocketClientAdapter wraps the raw ws
    # TunnelConnection wraps the adapter
    # receive_control returns mount_registered
    mock_conn = MagicMock()
    mock_conn.receive_control = AsyncMock(
        return_value={"type": "mount_registered", "code": assigned_code}
    )
    mock_conn.start_heartbeat = MagicMock()
    mock_conn.close = AsyncMock()
    mock_conn._ws = MagicMock()
    # _agent_receive_loop will call _ws.receive which raises ConnectionError to exit
    mock_conn._ws.receive = AsyncMock(side_effect=ConnectionError("ws closed"))

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
        patch("agent.connection.set_server_config"),
        patch("agent.connection.create_app", return_value=MagicMock()),
        patch("agent.connection.print_mounted"),
        patch("agent.connection.print_connected_status"),
    ):
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await connect_and_serve(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            preferred_code=None,
            password_hash=None,
            ttl_seconds=None,
        )

    assert result == assigned_code
    # Agent does NOT start its own heartbeat — relay initiates pings, agent responds
    mock_conn.start_heartbeat.assert_not_called()


@pytest.mark.asyncio
async def test_connect_and_serve_raises_on_wrong_control_type(tmp_path: Path) -> None:
    """connect_and_serve raises ValueError when first control message is not mount_registered."""
    from agent.connection import connect_and_serve

    mock_ws = MagicMock()
    mock_conn = MagicMock()
    mock_conn.receive_control = AsyncMock(
        return_value={"type": "unexpected_type", "code": "XYZ"}
    )
    mock_conn.close = AsyncMock()

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
    ):
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="mount_registered"):
            await connect_and_serve(
                relay_url="https://relay.example.com",
                folder=tmp_path,
                name="testfolder",
                preferred_code=None,
                password_hash=None,
                ttl_seconds=None,
            )


@pytest.mark.asyncio
async def test_run_agent_loop_retries_after_disconnect(tmp_path: Path) -> None:
    """Test 2: run_agent_loop retries after WebSocket disconnect with backoff delay."""
    from agent.connection import run_agent_loop

    call_count = 0

    async def fake_connect_and_serve(
        relay_url: str, folder: Path, name: str, preferred_code: str | None,
        password_hash: bytes | None, ttl_seconds: int | None,
    ) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("connection dropped")
        raise KeyboardInterrupt

    with (
        patch("agent.connection.connect_and_serve", side_effect=fake_connect_and_serve),
        patch("agent.connection.compute_backoff", return_value=0.0),
        patch("agent.connection.asyncio_sleep") as mock_sleep,
        patch("agent.connection.print_reconnect_status"),
    ):
        mock_sleep.return_value = None

        await run_agent_loop(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            password_hash=None,
            ttl_seconds=None,
        )

    assert call_count == 3
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_run_agent_loop_sends_preferred_code_on_reconnect(tmp_path: Path) -> None:
    """Test 3: run_agent_loop sends preferred code (last assigned code) on reconnect."""
    from agent.connection import run_agent_loop

    call_args_list = []

    async def fake_connect_and_serve(
        relay_url: str, folder: Path, name: str, preferred_code: str | None,
        password_hash: bytes | None, ttl_seconds: int | None,
    ) -> str:
        call_args_list.append(preferred_code)
        if len(call_args_list) == 1:
            return "MYCODE1"  # first connection succeeds, returns code
        if len(call_args_list) == 2:
            raise ConnectionError("dropped")
        raise KeyboardInterrupt

    with (
        patch("agent.connection.connect_and_serve", side_effect=fake_connect_and_serve),
        patch("agent.connection.compute_backoff", return_value=0.0),
        patch("agent.connection.asyncio_sleep", return_value=None),
        patch("agent.connection.print_reconnect_status"),
    ):
        await run_agent_loop(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            password_hash=None,
            ttl_seconds=None,
        )

    # First call: no preferred code (None)
    # Second call: preferred code from first successful connection
    assert call_args_list[0] is None
    assert call_args_list[1] == "MYCODE1"


@pytest.mark.asyncio
async def test_run_agent_loop_resets_attempt_counter_after_success(tmp_path: Path) -> None:
    """Test 4: run_agent_loop resets attempt counter after successful connection."""
    from agent.connection import run_agent_loop

    attempts_passed = []

    async def fake_connect_and_serve(
        relay_url: str, folder: Path, name: str, preferred_code: str | None
    ) -> str:
        return "ANYCODE"  # always succeeds

    call_count = 0

    def fake_compute_backoff(attempt: int, base: float, cap: float, jitter_factor: float) -> float:
        attempts_passed.append(attempt)
        return 0.0

    async def fake_sleep(delay: float) -> None:
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            raise KeyboardInterrupt

    # Simpler test: after success, next failure attempt counter starts at 1
    attempt_on_second_failure = []

    async def fake_connect_alternating(
        relay_url: str, folder: Path, name: str, preferred_code: str | None,
        password_hash: bytes | None, ttl_seconds: int | None,
    ) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "CODE1"  # success
        if call_count == 2:
            raise ConnectionError("dropped after reconnect")
        raise KeyboardInterrupt

    call_count = 0

    def fake_backoff(attempt: int, base: float, cap: float, jitter_factor: float) -> float:
        attempt_on_second_failure.append(attempt)
        return 0.0

    with (
        patch("agent.connection.connect_and_serve", side_effect=fake_connect_alternating),
        patch("agent.connection.compute_backoff", side_effect=fake_backoff),
        patch("agent.connection.asyncio_sleep", return_value=None),
        patch("agent.connection.print_reconnect_status"),
    ):
        await run_agent_loop(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            password_hash=None,
            ttl_seconds=None,
        )

    # After the first success and then failure, attempt should reset to 1
    assert attempt_on_second_failure == [1]


@pytest.mark.asyncio
async def test_agent_receive_loop_dispatches_open_frames(tmp_path: Path) -> None:
    """Test 5: OPEN frames received are dispatched as concurrent tasks via on_open callback."""
    from agent.connection import _agent_receive_loop

    import struct
    from tunnel.frames import serialize_frame
    from tunnel.enums import FrameType

    dispatched_ids: list[uuid.UUID] = []
    dispatched_tasks: list[asyncio.Task] = []

    async def fake_on_open(request_id: uuid.UUID) -> None:
        dispatched_ids.append(request_id)

    rid1 = uuid.uuid4()
    rid2 = uuid.uuid4()

    # Build raw OPEN frames
    frame1 = serialize_frame(FrameType.OPEN, rid1, json.dumps({"method": "GET", "path": "/a", "query": "", "headers": {}, "body": ""}).encode())
    frame2 = serialize_frame(FrameType.OPEN, rid2, json.dumps({"method": "GET", "path": "/b", "query": "", "headers": {}, "body": ""}).encode())

    # Use a call counter to interleave yields with event loop turns
    call_count = 0
    responses = [
        {"bytes": frame1},
        {"bytes": frame2},
    ]

    async def receive_with_yields() -> dict:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx < len(responses):
            await asyncio.sleep(0)  # yield control so previous task can run
            return responses[idx]
        raise ConnectionError("ws closed")

    conn = MagicMock()
    conn._ws = MagicMock()
    conn._dispatch_frame = MagicMock()
    conn.handle_pong = MagicMock()
    conn._ws.receive = receive_with_yields

    try:
        await _agent_receive_loop(conn, fake_on_open)
    except ConnectionError:
        pass

    # Give any remaining tasks a chance to complete
    await asyncio.sleep(0)

    assert len(dispatched_ids) == 2
    assert rid1 in dispatched_ids
    assert rid2 in dispatched_ids


@pytest.mark.asyncio
async def test_agent_receive_loop_dispatches_ws_open_frames() -> None:
    """WS_OPEN frames received cause handle_ws_open_frame to be dispatched as tasks."""
    from agent.connection import _agent_receive_loop_with_metadata
    from tunnel.frames import serialize_frame
    from tunnel.enums import FrameType
    from fastapi import FastAPI

    dispatched_ws_ids: list[uuid.UUID] = []
    dispatched_metadata: list[dict] = []

    ws_id = uuid.uuid4()
    ws_metadata = {"path": "/ws", "query": ""}
    ws_frame = serialize_frame(
        FrameType.WS_OPEN, ws_id, json.dumps(ws_metadata).encode()
    )

    call_count = 0

    async def receive_with_yields() -> dict:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 0:
            await asyncio.sleep(0)
            return {"bytes": ws_frame}
        raise ConnectionError("ws closed")

    conn = MagicMock()
    conn._ws = MagicMock()
    conn._dispatch_frame = MagicMock()
    conn.handle_pong = MagicMock()
    conn._ws.receive = receive_with_yields

    app = FastAPI()

    # Patch handle_ws_open_frame to capture calls
    with patch("agent.connection.handle_ws_open_frame") as mock_handle_ws:
        async def fake_handle_ws(conn, ws_id, metadata, asgi_app) -> None:
            dispatched_ws_ids.append(ws_id)
            dispatched_metadata.append(metadata)

        mock_handle_ws.side_effect = fake_handle_ws

        try:
            await _agent_receive_loop_with_metadata(conn, MagicMock(), app)
        except ConnectionError:
            pass

    await asyncio.sleep(0)

    assert len(dispatched_ws_ids) == 1
    assert dispatched_ws_ids[0] == ws_id
    assert dispatched_metadata[0]["path"] == "/ws"


@pytest.mark.asyncio
async def test_agent_receive_loop_responds_to_ping() -> None:
    """_agent_receive_loop sends pong when it receives a ping control message."""
    from agent.connection import _agent_receive_loop

    call_count = 0

    async def receive_ping_then_close() -> dict:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 0:
            return {"text": json.dumps({"type": "ping"})}
        raise ConnectionError("ws closed")

    conn = MagicMock()
    conn._ws = MagicMock()
    conn._ws.receive = receive_ping_then_close
    conn.handle_pong = MagicMock()
    conn.send_control = AsyncMock()

    try:
        await _agent_receive_loop(conn, AsyncMock())
    except ConnectionError:
        pass

    conn.send_control.assert_called_once_with({"type": "pong"})


@pytest.mark.asyncio
async def test_agent_receive_loop_with_metadata_responds_to_ping() -> None:
    """_agent_receive_loop_with_metadata sends pong when it receives a ping."""
    from agent.connection import _agent_receive_loop_with_metadata

    call_count = 0

    async def receive_ping_then_close() -> dict:
        nonlocal call_count
        idx = call_count
        call_count += 1
        if idx == 0:
            return {"text": json.dumps({"type": "ping"})}
        raise ConnectionError("ws closed")

    conn = MagicMock()
    conn._ws = MagicMock()
    conn._ws.receive = receive_ping_then_close
    conn.handle_pong = MagicMock()
    conn.send_control = AsyncMock()

    try:
        await _agent_receive_loop_with_metadata(conn, MagicMock(), MagicMock())
    except ConnectionError:
        pass

    conn.send_control.assert_called_once_with({"type": "pong"})
