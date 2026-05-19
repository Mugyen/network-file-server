"""Tests for TunnelConnection stream lifecycle, multiplexing, and control messaging."""

import asyncio
import json
import uuid

import pytest

from tunnel.connection import StreamState, TunnelConnection
from tunnel.constants import QUEUE_DEPTH
from tunnel.enums import FrameType
from tunnel.exceptions import (
    StreamLimitError,
    StreamNotFoundError,
    TunnelError,
)
from tunnel.frames import serialize_frame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_data_frame(request_id: uuid.UUID, payload: bytes) -> bytes:
    """Serialize a DATA frame for feeding into MockWebSocket."""
    return serialize_frame(FrameType.DATA, request_id, payload)


def make_close_frame(request_id: uuid.UUID) -> bytes:
    """Serialize a CLOSE frame for feeding into MockWebSocket."""
    return serialize_frame(FrameType.CLOSE, request_id, b"")


def make_cancel_frame(request_id: uuid.UUID) -> bytes:
    """Serialize a CANCEL frame for feeding into MockWebSocket."""
    return serialize_frame(FrameType.CANCEL, request_id, b"")


def make_error_frame(request_id: uuid.UUID) -> bytes:
    """Serialize an ERROR frame for feeding into MockWebSocket."""
    return serialize_frame(FrameType.ERROR, request_id, b"")


# ---------------------------------------------------------------------------
# Stream lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_stream_creates_stream_state(mock_ws):
    """open_stream returns a StreamState with correct initial state."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    state = conn.open_stream(rid)

    assert isinstance(state, StreamState)
    assert not state.closed.is_set()
    assert state.queue.empty()


@pytest.mark.asyncio
async def test_open_stream_duplicate_raises(mock_ws):
    """open_stream with duplicate request_id raises TunnelError."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    conn.open_stream(rid)

    with pytest.raises(TunnelError):
        conn.open_stream(rid)


@pytest.mark.asyncio
async def test_open_stream_at_limit_raises(mock_ws):
    """open_stream when at MAX_STREAMS (100) raises StreamLimitError."""
    conn = TunnelConnection(mock_ws)

    for _ in range(100):
        conn.open_stream(uuid.uuid4())

    with pytest.raises(StreamLimitError):
        conn.open_stream(uuid.uuid4())


@pytest.mark.asyncio
async def test_dispatch_data_to_open_stream(mock_ws):
    """DATA frame dispatched to open stream puts payload in that stream's queue."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)
    payload = b"hello world"

    await conn._dispatch_frame(FrameType.DATA, rid, payload)

    assert not state.queue.empty()
    queued = state.queue.get_nowait()
    assert queued == payload


@pytest.mark.asyncio
async def test_dispatch_data_to_nonexistent_stream_is_ignored(mock_ws):
    """DATA frame to non-existent stream is silently ignored (teardown race)."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    # Should not raise — frames for missing streams are normal during teardown
    await conn._dispatch_frame(FrameType.DATA, rid, b"payload")


@pytest.mark.asyncio
async def test_close_frame_sets_closed_event_and_removes_stream(mock_ws):
    """CLOSE frame sets stream.closed event and removes stream from tracking dict."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)

    await conn._dispatch_frame(FrameType.CLOSE, rid, b"")

    assert state.closed.is_set()
    # Stream stays until consumer calls remove_stream (avoids race with StreamingResponse)
    assert conn.get_stream(rid) is state
    conn.remove_stream(rid)
    with pytest.raises(StreamNotFoundError):
        conn.get_stream(rid)


@pytest.mark.asyncio
async def test_cancel_frame_sets_closed_event_and_removes_stream(mock_ws):
    """CANCEL frame sets stream.closed event and removes stream from tracking dict."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)

    await conn._dispatch_frame(FrameType.CANCEL, rid, b"")

    assert state.closed.is_set()
    # Stream stays until consumer calls remove_stream
    assert conn.get_stream(rid) is state
    conn.remove_stream(rid)
    with pytest.raises(StreamNotFoundError):
        conn.get_stream(rid)


@pytest.mark.asyncio
async def test_error_frame_sets_closed_event_and_removes_stream(mock_ws):
    """ERROR frame sets stream.closed event and removes stream from tracking dict."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)

    await conn._dispatch_frame(FrameType.ERROR, rid, b"")

    assert state.closed.is_set()
    assert conn.get_stream(rid) is state
    conn.remove_stream(rid)
    with pytest.raises(StreamNotFoundError):
        conn.get_stream(rid)


@pytest.mark.asyncio
async def test_get_stream_raises_for_unknown_id(mock_ws):
    """get_stream raises StreamNotFoundError for unknown UUID."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    with pytest.raises(StreamNotFoundError):
        conn.get_stream(rid)


# ---------------------------------------------------------------------------
# Multiplexing tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_streams_receive_own_data_without_cross_contamination(mock_ws):
    """Stream A and Stream B receive their own data without cross-contamination."""
    conn = TunnelConnection(mock_ws)
    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()
    state_a = conn.open_stream(rid_a)
    state_b = conn.open_stream(rid_b)

    payload_a = b"stream-a-data"
    payload_b = b"stream-b-data"

    await conn._dispatch_frame(FrameType.DATA, rid_a, payload_a)
    await conn._dispatch_frame(FrameType.DATA, rid_b, payload_b)

    assert state_a.queue.get_nowait() == payload_a
    assert state_b.queue.get_nowait() == payload_b
    assert state_a.queue.empty()
    assert state_b.queue.empty()


@pytest.mark.asyncio
async def test_multiple_data_frames_per_stream_correct_counts(mock_ws):
    """Stream A with 3 DATA frames and Stream B with 2 DATA frames — each queue has correct count."""
    conn = TunnelConnection(mock_ws)
    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()
    state_a = conn.open_stream(rid_a)
    state_b = conn.open_stream(rid_b)

    for i in range(3):
        await conn._dispatch_frame(FrameType.DATA, rid_a, f"a-frame-{i}".encode())
    for i in range(2):
        await conn._dispatch_frame(FrameType.DATA, rid_b, f"b-frame-{i}".encode())

    assert state_a.queue.qsize() == 3
    assert state_b.queue.qsize() == 2


@pytest.mark.asyncio
async def test_dispatch_blocks_under_backpressure_instead_of_raising(mock_ws):
    """A full stream queue makes _dispatch_frame block, not raise QueueFull.

    Regression: previously put_nowait raised asyncio.QueueFull on a slow
    consumer (e.g. a browser pulling a media preview), which propagated out
    of the receive loop and tore down the entire agent tunnel.
    """
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)

    # Fill the bounded queue exactly to capacity.
    for _ in range(QUEUE_DEPTH):
        await conn._dispatch_frame(FrameType.DATA, rid, b"x")
    assert state.queue.full()

    # One more frame must block (backpressure), never raise QueueFull.
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            conn._dispatch_frame(FrameType.DATA, rid, b"overflow"),
            timeout=0.1,
        )

    # Draining one item lets a subsequent dispatch complete promptly.
    assert state.queue.get_nowait() == b"x"
    await asyncio.wait_for(
        conn._dispatch_frame(FrameType.DATA, rid, b"after-drain"),
        timeout=0.5,
    )
    assert state.queue.full()


@pytest.mark.asyncio
async def test_cancel_stream_a_does_not_affect_stream_b(mock_ws):
    """CANCEL on Stream A does not affect Stream B."""
    conn = TunnelConnection(mock_ws)
    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()
    state_a = conn.open_stream(rid_a)
    state_b = conn.open_stream(rid_b)

    await conn._dispatch_frame(FrameType.CANCEL, rid_a, b"")

    # Stream A is closed
    assert state_a.closed.is_set()
    # Stream B is still open
    assert not state_b.closed.is_set()
    assert conn.get_stream(rid_b) is state_b


# ---------------------------------------------------------------------------
# Sending tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_data_serializes_and_sends_binary_frame(mock_ws):
    """send_data serializes and sends binary frame via ws.send_bytes."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    payload = b"test payload"

    await conn.send_data(rid, payload)

    assert len(mock_ws.sent_bytes_frames) == 1
    frame = mock_ws.sent_bytes_frames[0]
    # Verify it deserializes correctly
    from tunnel.frames import deserialize_frame
    frame_type, decoded_rid, decoded_payload = deserialize_frame(frame)
    assert frame_type == FrameType.DATA
    assert decoded_rid == rid
    assert decoded_payload == payload


@pytest.mark.asyncio
async def test_send_open_serializes_open_frame_with_json_metadata(mock_ws):
    """send_open serializes OPEN frame with JSON metadata as payload, sends binary."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    metadata = {"method": "GET", "path": "/api/files"}

    await conn.send_open(rid, metadata)

    assert len(mock_ws.sent_bytes_frames) == 1
    from tunnel.frames import deserialize_frame
    frame_type, decoded_rid, decoded_payload = deserialize_frame(mock_ws.sent_bytes_frames[0])
    assert frame_type == FrameType.OPEN
    assert decoded_rid == rid
    decoded_metadata = json.loads(decoded_payload.decode("utf-8"))
    assert decoded_metadata == metadata


@pytest.mark.asyncio
async def test_send_close_serializes_close_frame_with_empty_payload(mock_ws):
    """send_close serializes CLOSE frame with empty payload, sends binary."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    await conn.send_close(rid)

    assert len(mock_ws.sent_bytes_frames) == 1
    from tunnel.frames import deserialize_frame
    frame_type, decoded_rid, decoded_payload = deserialize_frame(mock_ws.sent_bytes_frames[0])
    assert frame_type == FrameType.CLOSE
    assert decoded_rid == rid
    assert decoded_payload == b""


@pytest.mark.asyncio
async def test_send_cancel_serializes_cancel_frame_with_empty_payload(mock_ws):
    """send_cancel serializes CANCEL frame with empty payload, sends binary."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()

    await conn.send_cancel(rid)

    assert len(mock_ws.sent_bytes_frames) == 1
    from tunnel.frames import deserialize_frame
    frame_type, decoded_rid, decoded_payload = deserialize_frame(mock_ws.sent_bytes_frames[0])
    assert frame_type == FrameType.CANCEL
    assert decoded_rid == rid
    assert decoded_payload == b""


# ---------------------------------------------------------------------------
# Control message tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_control_sends_json_text_frame(mock_ws):
    """send_control sends JSON text frame via ws.send_text."""
    conn = TunnelConnection(mock_ws)
    message = {"type": "ping"}

    await conn.send_control(message)

    assert len(mock_ws.sent_text_frames) == 1
    decoded = json.loads(mock_ws.sent_text_frames[0])
    assert decoded == message


@pytest.mark.asyncio
async def test_send_control_without_type_raises(mock_ws):
    """send_control without 'type' key raises TunnelError."""
    conn = TunnelConnection(mock_ws)

    with pytest.raises(TunnelError):
        await conn.send_control({"data": "no type key"})


@pytest.mark.asyncio
async def test_receive_loop_dispatches_binary_frame_to_stream(mock_ws):
    """Receiving binary frame dispatches deserialized frame to correct stream by request_id.

    The receive loop runs forever, so we cancel it after the frames are consumed
    and verify the side effects (queue populated, stream closed).
    """
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)
    payload = b"binary dispatch test"

    # Feed a DATA frame then a CLOSE frame
    mock_ws.feed_binary(make_data_frame(rid, payload))
    mock_ws.feed_binary(make_close_frame(rid))

    # Run the loop in a task and cancel after all queued frames have been consumed
    task = asyncio.create_task(conn.run_receive_loop())
    # Wait until the inbound queue is drained (both frames processed)
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # DATA payload must be in the stream queue
    assert state.queue.get_nowait() == payload
    # CLOSE frame must have set closed event and removed stream
    assert state.closed.is_set()


@pytest.mark.asyncio
async def test_receive_loop_dispatches_text_frame_to_control_handler(mock_ws):
    """Receiving text frame dispatches to control handler (pong wires correctly)."""
    conn = TunnelConnection(mock_ws)

    # Feed a pong text frame
    mock_ws.feed_text(json.dumps({"type": "pong"}))

    # Run the loop in a task, give it time to process the one text frame, then cancel
    task = asyncio.create_task(conn.run_receive_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # No crash = success. The pong was handled by handle_pong internally.
    # No outbound bytes should have been sent.
    assert len(mock_ws.sent_bytes_frames) == 0


# ---------------------------------------------------------------------------
# Backpressure tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backpressure_blocks():
    """Filling queue to capacity (64 frames) and adding one more blocks the put() call.

    We verify this by confirming that asyncio.wait_for on a 65th put() raises
    TimeoutError — proof the sender is blocked awaiting a consumer.
    """
    from tunnel.constants import QUEUE_DEPTH
    q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_DEPTH)

    # Fill queue to capacity
    for i in range(QUEUE_DEPTH):
        q.put_nowait(f"frame-{i}".encode())

    assert q.full()

    # 65th put() should block; wait_for with short timeout should time out
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.put(b"one-too-many"), timeout=0.05)


@pytest.mark.asyncio
async def test_no_frame_drop():
    """No frames are dropped — all QUEUE_DEPTH + 1 frames are eventually received.

    Producer fills the queue then adds one more after a consumer reads one.
    """
    from tunnel.constants import QUEUE_DEPTH
    q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_DEPTH)

    frames_sent = QUEUE_DEPTH + 1

    async def producer():
        for i in range(frames_sent):
            await q.put(f"frame-{i}".encode())

    async def consumer():
        received = []
        for _ in range(frames_sent):
            received.append(await q.get())
        return received

    _, results = await asyncio.gather(producer(), consumer())
    assert len(results) == frames_sent


@pytest.mark.asyncio
async def test_backpressure_per_stream(mock_ws):
    """Backpressure is per-stream — filling Stream A queue does not block Stream B.

    Stream A's queue is full, but Stream B should still accept frames immediately.
    """
    from tunnel.constants import QUEUE_DEPTH
    conn = TunnelConnection(mock_ws)
    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()
    state_a = conn.open_stream(rid_a)
    state_b = conn.open_stream(rid_b)

    # Fill Stream A to capacity
    for i in range(QUEUE_DEPTH):
        state_a.queue.put_nowait(f"frame-{i}".encode())

    assert state_a.queue.full()
    assert not state_b.queue.full()

    # Stream B should still accept frames immediately
    state_b.queue.put_nowait(b"stream-b-frame")
    assert state_b.queue.qsize() == 1


# ---------------------------------------------------------------------------
# Heartbeat tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_sends_ping(mock_ws):
    """start_heartbeat creates a background task that sends ping control messages."""
    conn = TunnelConnection(mock_ws)

    # Use a very short interval for testing (0.05s)
    conn.start_heartbeat(heartbeat_interval_s=0.05, missed_limit=3)

    # Wait long enough for at least one ping to be sent
    await asyncio.sleep(0.15)

    # Cancel the heartbeat task cleanly
    await conn.close()

    # At least one ping text frame should have been sent
    pings = [f for f in mock_ws.sent_text_frames if json.loads(f).get("type") == "ping"]
    assert len(pings) >= 1


@pytest.mark.asyncio
async def test_heartbeat_pong_resets_missed(mock_ws):
    """When pong is received within the interval, missed counter resets — no teardown."""
    conn = TunnelConnection(mock_ws)

    conn.start_heartbeat(heartbeat_interval_s=0.05, missed_limit=3)

    # Respond to pings with pong
    for _ in range(5):
        await asyncio.sleep(0.06)
        conn.handle_pong()

    # Connection must NOT have torn down — streams can still be opened
    new_stream = conn.open_stream(uuid.uuid4())
    assert not new_stream.closed.is_set()

    await conn.close()


@pytest.mark.asyncio
async def test_heartbeat_timeout_tears_down(mock_ws):
    """After HEARTBEAT_MISSED_LIMIT consecutive missed pongs, all streams are closed."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)

    # Use short interval so the test completes quickly; missed_limit = 3
    conn.start_heartbeat(heartbeat_interval_s=0.05, missed_limit=3)

    # Wait for 3 missed pongs: 3 intervals + a bit of slack
    await asyncio.sleep(0.5)

    # All streams should be closed after teardown
    assert state.closed.is_set()
    assert conn._closed is True


@pytest.mark.asyncio
async def test_stop_cancels_heartbeat(mock_ws):
    """start_heartbeat followed by close() cancels the heartbeat task cleanly."""
    conn = TunnelConnection(mock_ws)
    conn.start_heartbeat(heartbeat_interval_s=10.0, missed_limit=3)

    task = conn._heartbeat_task
    assert task is not None
    assert not task.done()

    await conn.close()

    assert task.done()


@pytest.mark.asyncio
async def test_receive_loop_responds_to_ping_with_pong(mock_ws):
    """run_receive_loop sends a pong control message when it receives a ping."""
    conn = TunnelConnection(mock_ws)

    mock_ws.feed_text(json.dumps({"type": "ping"}))

    loop_task = asyncio.create_task(conn.run_receive_loop())
    # Give the loop time to process the ping and send the pong
    await asyncio.sleep(0.05)
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    assert len(mock_ws.sent_text_frames) == 1
    response = json.loads(mock_ws.sent_text_frames[0])
    assert response == {"type": "pong"}


# ---------------------------------------------------------------------------
# First-byte timeout tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_byte_timeout_raises(mock_ws):
    """read_stream raises FirstByteTimeoutError when no data arrives within timeout_s."""
    from tunnel.exceptions import FirstByteTimeoutError

    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    conn.open_stream(rid)

    with pytest.raises(FirstByteTimeoutError):
        await conn.read_stream(rid, timeout_s=0.05)


@pytest.mark.asyncio
async def test_first_byte_within_timeout(mock_ws):
    """read_stream returns data when first byte arrives within timeout_s."""
    conn = TunnelConnection(mock_ws)
    rid = uuid.uuid4()
    state = conn.open_stream(rid)
    expected = b"first byte payload"

    # Deliver data slightly after the read_stream call starts
    async def deliver():
        await asyncio.sleep(0.02)
        state.queue.put_nowait(expected)

    data, _ = await asyncio.gather(conn.read_stream(rid, timeout_s=1.0), deliver())
    assert data == expected


# ---------------------------------------------------------------------------
# Teardown tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_idempotent(mock_ws):
    """Calling close() twice raises no exception."""
    conn = TunnelConnection(mock_ws)

    await conn.close()
    await conn.close()  # Must not raise


# ---------------------------------------------------------------------------
# Control handler dispatch tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_control_handler_dispatch(mock_ws):
    """TunnelConnection with a registered control handler dispatches non-ping/pong messages to it."""
    conn = TunnelConnection(mock_ws)
    received: list[dict] = []

    async def handler(msg: dict) -> None:
        received.append(msg)

    conn.set_control_handler(handler)

    # Feed a delete_expired_files message then a disconnect
    mock_ws.feed_text(json.dumps({"type": "delete_expired_files", "code": "abc"}))

    task = asyncio.create_task(conn.run_receive_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert len(received) == 1
    assert received[0]["type"] == "delete_expired_files"
    assert received[0]["code"] == "abc"


@pytest.mark.asyncio
async def test_control_handler_not_called_for_ping_pong(mock_ws):
    """ping/pong messages are handled by the tunnel, not forwarded to control handler."""
    conn = TunnelConnection(mock_ws)
    received: list[dict] = []

    async def handler(msg: dict) -> None:
        received.append(msg)

    conn.set_control_handler(handler)

    # Feed a pong message then cancel
    mock_ws.feed_text(json.dumps({"type": "pong"}))

    task = asyncio.create_task(conn.run_receive_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Control handler should NOT have been called for pong
    assert len(received) == 0


@pytest.mark.asyncio
async def test_no_control_handler_silently_drops(mock_ws):
    """Unknown message type with no handler set completes without error."""
    conn = TunnelConnection(mock_ws)

    # Feed an unknown message type -- no control handler set
    mock_ws.feed_text(json.dumps({"type": "unknown_msg", "data": "test"}))

    task = asyncio.create_task(conn.run_receive_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # No crash = success


# ---------------------------------------------------------------------------
# Teardown tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_cancels_heartbeat_and_streams(mock_ws):
    """close() cancels the heartbeat task and closes all open streams."""
    conn = TunnelConnection(mock_ws)
    rid_a = uuid.uuid4()
    rid_b = uuid.uuid4()
    state_a = conn.open_stream(rid_a)
    state_b = conn.open_stream(rid_b)

    # Use long interval so heartbeat doesn't fire before close()
    conn.start_heartbeat(heartbeat_interval_s=60.0, missed_limit=3)
    task = conn._heartbeat_task

    await conn.close()

    # Heartbeat task must be done (cancelled)
    assert task.done()
    # All streams must be closed
    assert state_a.closed.is_set()
    assert state_b.closed.is_set()
