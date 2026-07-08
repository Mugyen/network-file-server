"""Tests for agent connection loop and reconnect behavior."""

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tunnel.constants import AGENT_HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT



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
    mock_conn.send_control = AsyncMock()
    mock_conn.set_control_handler = MagicMock()
    mock_conn._ws = MagicMock()
    # The receive loop raises ConnectionError to simulate a clean disconnect.
    mock_conn.run_receive_loop_with_handlers = AsyncMock(
        side_effect=ConnectionError("ws closed")
    )

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
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
            owner=None,
            app_factory=lambda ctx: MagicMock(),
        )

    assert result == assigned_code
    # Agent does NOT start its own heartbeat — relay initiates pings, agent responds
    # Phase-4 hardening: the agent now runs its own (slower) heartbeat so a
    # half-dead relay socket is detected instead of silently believed online.
    mock_conn.start_heartbeat.assert_called_once_with(
        AGENT_HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT
    )


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
    mock_conn.send_control = AsyncMock()

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
                owner=None,
                app_factory=lambda ctx: MagicMock(),
            )


@pytest.mark.asyncio
async def test_run_agent_loop_retries_after_disconnect(tmp_path: Path) -> None:
    """Test 2: run_agent_loop retries after WebSocket disconnect with backoff delay."""
    from agent.connection import run_agent_loop

    call_count = 0

    async def fake_connect_and_serve(
        relay_url: str, folder: Path, name: str, preferred_code: str | None,
        password_hash: bytes | None, ttl_seconds: int | None, owner=None, app_factory=None,
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
            owner=None,
            app_factory=lambda ctx: MagicMock(),
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
        password_hash: bytes | None, ttl_seconds: int | None, owner=None, app_factory=None,
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
            owner=None,
            app_factory=lambda ctx: MagicMock(),
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
        password_hash: bytes | None, ttl_seconds: int | None, owner=None, app_factory=None,
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
            owner=None,
            app_factory=lambda ctx: MagicMock(),
        )

    # After the first success and then failure, attempt should reset to 1
    assert attempt_on_second_failure == [1]


# Receive-loop wiring lives in TunnelConnection now; the agent provides
# OPEN/WS_OPEN handlers via _OpenFrameHandlers (ping/pong routing is covered
# by tests/tunnel/test_connection.py). These tests cover that handler class.


@pytest.mark.asyncio
async def test_open_frame_handlers_dispatch_open() -> None:
    """_OpenFrameHandlers.on_open opens the stream and spawns handle_open_frame."""
    from agent.connection import _OpenFrameHandlers
    from tunnel.metadata import RequestMetadata

    conn = MagicMock()
    conn.open_stream = MagicMock()
    payload = RequestMetadata(
        method="GET", path="/a", query="", headers={}, content_length=0
    ).to_payload()
    rid = uuid.uuid4()

    dispatched: list[uuid.UUID] = []

    async def fake_handle_open(c, request_id, metadata, client) -> None:
        dispatched.append(request_id)

    handlers = _OpenFrameHandlers(conn, MagicMock(), MagicMock())
    with patch("agent.connection.handle_open_frame", side_effect=fake_handle_open):
        await handlers.on_open(rid, payload)
        await handlers.drain()

    conn.open_stream.assert_called_once_with(rid)
    assert dispatched == [rid]


@pytest.mark.asyncio
async def test_open_frame_handlers_dispatch_ws_open() -> None:
    """_OpenFrameHandlers.on_ws_open spawns handle_ws_open_frame with parsed metadata."""
    from agent.connection import _OpenFrameHandlers
    from tunnel.metadata import WsOpenMetadata

    ws_id = uuid.uuid4()
    payload = WsOpenMetadata(path="/ws", query="", headers={}).to_payload()
    conn = MagicMock()

    dispatched_meta: list = []

    async def fake_handle_ws(c, request_id, metadata, app) -> None:
        dispatched_meta.append(metadata)

    handlers = _OpenFrameHandlers(conn, MagicMock(), MagicMock())
    with patch("agent.connection.handle_ws_open_frame", side_effect=fake_handle_ws):
        await handlers.on_ws_open(ws_id, payload)
        await handlers.drain()

    conn.open_stream.assert_called_once_with(ws_id)
    assert len(dispatched_meta) == 1
    assert dispatched_meta[0].path == "/ws"


@pytest.mark.asyncio
async def test_ws_open_registers_stream_before_back_to_back_data() -> None:
    """Back-to-back WS_OPEN + WS_DATA queues the first message instead of dropping it."""
    from agent.connection import _OpenFrameHandlers
    from tunnel.connection import TunnelConnection
    from tunnel.enums import FrameType
    from tunnel.frames import serialize_frame
    from tunnel.metadata import WsOpenMetadata

    ws_id = uuid.uuid4()
    first_payload = b"first browser message"
    ws = MagicMock()
    ws.receive = AsyncMock(
        side_effect=[
            {
                "bytes": serialize_frame(
                    FrameType.WS_OPEN,
                    ws_id,
                    WsOpenMetadata(path="/ws", query="", headers={}).to_payload(),
                )
            },
            {"bytes": serialize_frame(FrameType.WS_DATA, ws_id, first_payload)},
            {"type": "websocket.disconnect"},
        ]
    )
    conn = TunnelConnection(ws)
    release_handler = asyncio.Event()

    async def fake_handle_ws(c, request_id, metadata, app) -> None:
        await release_handler.wait()

    handlers = _OpenFrameHandlers(conn, MagicMock(), MagicMock())
    with patch("agent.connection.handle_ws_open_frame", side_effect=fake_handle_ws):
        await conn.run_receive_loop_with_handlers(handlers.on_open, handlers.on_ws_open)
        state = conn.get_stream(ws_id)
        assert state.queue.get_nowait() == first_payload
        release_handler.set()
        await handlers.drain()


@pytest.mark.asyncio
async def test_open_frame_handlers_reject_malformed_open() -> None:
    """A malformed OPEN payload answers 400 and does not spawn a handler."""
    from agent.connection import _OpenFrameHandlers

    conn = MagicMock()
    conn.send_data = AsyncMock()
    conn.send_close = AsyncMock()
    conn.open_stream = MagicMock()

    handlers = _OpenFrameHandlers(conn, MagicMock(), MagicMock())
    with patch("agent.connection.handle_open_frame") as mock_handle:
        await handlers.on_open(uuid.uuid4(), b"not valid json")
        await handlers.drain()

    mock_handle.assert_not_called()
    conn.open_stream.assert_not_called()
    # _reject_open sent a 400 status frame.
    assert conn.send_data.await_count == 1
    sent_payload = conn.send_data.await_args.args[1]
    assert b'"status": 400' in sent_payload
