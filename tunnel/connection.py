"""TunnelConnection — WebSocket multiplexing with per-stream queues and lifecycle management."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field

from tunnel.constants import MAX_STREAMS, QUEUE_DEPTH
from tunnel.enums import FrameType
from tunnel.exceptions import (
    FirstByteTimeoutError,
    StreamLimitError,
    StreamNotFoundError,
    TunnelError,
)
from tunnel.frames import deserialize_frame, serialize_frame
from tunnel.protocol import WebSocketProtocol


@dataclass
class StreamState:
    """Per-stream state tracking for a single multiplexed request.

    Attributes:
        queue:  Bounded asyncio queue holding inbound DATA payloads for this stream.
        closed: Event set when the stream receives CLOSE, CANCEL, or ERROR.
    """

    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=QUEUE_DEPTH))
    closed: asyncio.Event = field(default_factory=asyncio.Event)


class TunnelConnection:
    """High-level abstraction over a WebSocket with stream multiplexing.

    Wraps a WebSocketProtocol to provide:
    - Stream lifecycle (open, close, cancel, error) with UUID correlation
    - Per-stream bounded asyncio.Queue for backpressure
    - Control message (ping/pong, mount registration) handling via JSON text frames
    - Data frames via binary WebSocket frames
    - Heartbeat management (start_heartbeat / handle_pong / stop)
    - Idempotent close() that cancels heartbeat and drains all streams
    """

    def __init__(self, ws: WebSocketProtocol) -> None:
        """Initialise the connection around a WebSocket.

        Args:
            ws: Any object implementing WebSocketProtocol (FastAPI WS or MockWebSocket).
        """
        self._ws = ws
        self._streams: dict[uuid.UUID, StreamState] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._pong_event: asyncio.Event = asyncio.Event()
        self._closed: bool = False

    # ------------------------------------------------------------------
    # Stream lifecycle
    # ------------------------------------------------------------------

    def open_stream(self, request_id: uuid.UUID) -> StreamState:
        """Register a new stream and return its StreamState.

        Args:
            request_id: UUID that uniquely identifies this request stream.

        Returns:
            A fresh StreamState with an empty bounded queue.

        Raises:
            StreamLimitError:  When MAX_STREAMS active streams already exist.
            TunnelError:       When request_id is already registered.
        """
        if len(self._streams) >= MAX_STREAMS:
            raise StreamLimitError(
                f"Cannot open stream {request_id}: already at limit of {MAX_STREAMS} streams"
            )
        if request_id in self._streams:
            raise TunnelError(f"Stream {request_id} is already open")

        state = StreamState()
        self._streams[request_id] = state
        return state

    def close_stream(self, request_id: uuid.UUID) -> None:
        """Signal a stream as closed so consumers can drain and exit.

        Sets the stream's closed event. Does NOT remove the stream from the
        tracking dict — the consumer (read_stream_iter) calls remove_stream
        after draining. This avoids a race where a fast CLOSE arrives before
        the StreamingResponse starts iterating.

        Args:
            request_id: UUID of the stream to close.

        Raises:
            StreamNotFoundError: When request_id is not registered.
        """
        state = self.get_stream(request_id)
        state.closed.set()

    def remove_stream(self, request_id: uuid.UUID) -> None:
        """Remove a stream from the tracking dict after the consumer has drained it.

        Args:
            request_id: UUID of the stream to remove.
        """
        self._streams.pop(request_id, None)

    def get_stream(self, request_id: uuid.UUID) -> StreamState:
        """Return the StreamState for an active stream.

        Args:
            request_id: UUID of the stream to look up.

        Returns:
            The StreamState for that stream.

        Raises:
            StreamNotFoundError: When request_id is not registered.
        """
        state = self._streams.get(request_id)
        if state is None:
            raise StreamNotFoundError(f"Stream {request_id} not found")
        return state

    def _dispatch_frame(
        self, frame_type: FrameType, request_id: uuid.UUID, payload: bytes
    ) -> None:
        """Route an inbound frame to the correct stream or lifecycle handler.

        - DATA/WS_DATA → put payload into stream queue (blocks under backpressure
                         when called via asyncio — use put_nowait only in tests).
        - CLOSE/CANCEL/ERROR/WS_CLOSE → call close_stream to signal and deregister.

        Silently ignores frames for streams that have already been closed and
        removed — this is normal during WebSocket teardown when both sides
        race to send CLOSE/WS_CLOSE.

        Args:
            frame_type: Parsed FrameType from the wire.
            request_id: UUID correlating the frame to a stream.
            payload:    Binary payload extracted from the frame.
        """
        try:
            if frame_type in (FrameType.DATA, FrameType.WS_DATA):
                state = self.get_stream(request_id)
                state.queue.put_nowait(payload)
            elif frame_type in (FrameType.CLOSE, FrameType.CANCEL, FrameType.ERROR, FrameType.WS_CLOSE):
                self.close_stream(request_id)
        except StreamNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Sending — binary data frames
    # ------------------------------------------------------------------

    async def send_data(self, request_id: uuid.UUID, payload: bytes) -> None:
        """Serialize and send a DATA binary frame.

        Args:
            request_id: UUID correlating this data to an open stream on the receiver.
            payload:    Raw bytes to transmit.
        """
        frame = serialize_frame(FrameType.DATA, request_id, payload)
        await self._ws.send_bytes(frame)

    async def send_open(self, request_id: uuid.UUID, metadata: dict) -> None:
        """Serialize and send an OPEN binary frame with JSON metadata payload.

        Args:
            request_id: UUID for the new stream being opened.
            metadata:   Dict of request metadata (method, path, headers, etc.).
        """
        payload = json.dumps(metadata).encode("utf-8")
        frame = serialize_frame(FrameType.OPEN, request_id, payload)
        await self._ws.send_bytes(frame)

    async def send_close(self, request_id: uuid.UUID) -> None:
        """Serialize and send a CLOSE binary frame with empty payload.

        Args:
            request_id: UUID of the stream being closed.
        """
        frame = serialize_frame(FrameType.CLOSE, request_id, b"")
        await self._ws.send_bytes(frame)

    async def send_cancel(self, request_id: uuid.UUID) -> None:
        """Serialize and send a CANCEL binary frame with empty payload.

        Args:
            request_id: UUID of the stream being cancelled.
        """
        frame = serialize_frame(FrameType.CANCEL, request_id, b"")
        await self._ws.send_bytes(frame)

    async def send_ws_open(self, ws_id: uuid.UUID, metadata: dict) -> None:
        """Serialize and send a WS_OPEN binary frame with JSON metadata payload.

        Args:
            ws_id:    UUID for the new WebSocket stream being opened.
            metadata: Dict of WebSocket metadata (path, query).
        """
        payload = json.dumps(metadata).encode("utf-8")
        frame = serialize_frame(FrameType.WS_OPEN, ws_id, payload)
        await self._ws.send_bytes(frame)

    async def send_ws_data(self, ws_id: uuid.UUID, payload: bytes) -> None:
        """Serialize and send a WS_DATA binary frame with the given payload.

        Args:
            ws_id:   UUID of the WebSocket stream.
            payload: Raw bytes from the WebSocket message to transmit.
        """
        frame = serialize_frame(FrameType.WS_DATA, ws_id, payload)
        await self._ws.send_bytes(frame)

    async def send_ws_close(self, ws_id: uuid.UUID) -> None:
        """Serialize and send a WS_CLOSE binary frame with empty payload.

        Args:
            ws_id: UUID of the WebSocket stream being closed.
        """
        frame = serialize_frame(FrameType.WS_CLOSE, ws_id, b"")
        await self._ws.send_bytes(frame)

    # ------------------------------------------------------------------
    # Control messages — JSON text frames
    # ------------------------------------------------------------------

    async def send_control(self, message: dict) -> None:
        """Validate and send a JSON control message as a text frame.

        Args:
            message: Dict that MUST contain a "type" key.

        Raises:
            TunnelError: When "type" key is absent from message.
        """
        if "type" not in message:
            raise TunnelError(
                f"Control message must contain a 'type' key, got keys: {list(message.keys())}"
            )
        await self._ws.send_text(json.dumps(message))

    async def receive_control(self) -> dict:
        """Receive a JSON control text frame and validate it has a 'type' key.

        Returns:
            Parsed dict with at least a "type" key.

        Raises:
            TunnelError: When received JSON has no "type" key.
        """
        text = await self._ws.receive_text()
        message: dict = json.loads(text)
        if "type" not in message:
            raise TunnelError(
                f"Received control message has no 'type' key, got keys: {list(message.keys())}"
            )
        return message

    # ------------------------------------------------------------------
    # Receive loop — dispatches binary and text frames
    # ------------------------------------------------------------------

    async def run_receive_loop(self) -> None:
        """Async loop that reads frames from the WebSocket and dispatches them.

        - Binary frames are deserialized and routed to _dispatch_frame.
        - Text frames are parsed as JSON control messages; "pong" calls handle_pong().
        - Disconnect messages (no "bytes" or "text" key) break the loop.

        Runs until the WebSocket is closed or an unrecoverable error occurs.
        """
        while True:
            frame_dict = await self._ws.receive()
            if "bytes" in frame_dict:
                raw = frame_dict["bytes"]
                frame_type, request_id, payload = deserialize_frame(raw)
                self._dispatch_frame(frame_type, request_id, payload)
            elif "text" in frame_dict:
                text = frame_dict["text"]
                message: dict = json.loads(text)
                if message.get("type") == "pong":
                    self.handle_pong()
                elif message.get("type") == "ping":
                    await self.send_control({"type": "pong"})
            else:
                # Starlette sends {"type": "websocket.disconnect"} on close —
                # no "bytes" or "text" key present. Break to avoid calling
                # receive() again which raises RuntimeError.
                break

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def start_heartbeat(self, heartbeat_interval_s: float, missed_limit: int) -> None:
        """Start a background heartbeat task.

        Sends a {"type": "ping"} control message every heartbeat_interval_s.
        After missed_limit consecutive missed pongs, calls _tear_down().

        Args:
            heartbeat_interval_s: Seconds between each ping transmission.
            missed_limit:         Number of consecutive missed pongs before teardown.
        """
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(heartbeat_interval_s, missed_limit)
        )

    async def _heartbeat_loop(
        self, heartbeat_interval_s: float, missed_limit: int
    ) -> None:
        """Internal heartbeat coroutine — sends pings and counts missed pongs."""
        missed = 0
        while not self._closed:
            await asyncio.sleep(heartbeat_interval_s)
            self._pong_event.clear()
            await self.send_control({"type": "ping"})

            try:
                await asyncio.wait_for(
                    self._pong_event.wait(),
                    timeout=heartbeat_interval_s,
                )
                missed = 0
            except asyncio.TimeoutError:
                missed += 1
                if missed >= missed_limit:
                    self._tear_down(
                        f"Heartbeat timeout: {missed} consecutive missed pongs"
                    )
                    return

    def handle_pong(self) -> None:
        """Signal that a pong was received, resetting the heartbeat missed counter."""
        self._pong_event.set()

    def _tear_down(self, reason: str) -> None:
        """Close all open streams and mark the connection as closed.

        Args:
            reason: Human-readable description of why the connection is being torn down.
        """
        if self._closed:
            return
        self._closed = True
        # Close all streams — snapshot the keys since we modify the dict
        for rid in list(self._streams.keys()):
            state = self._streams.get(rid)
            if state is not None:
                state.closed.set()
        self._streams.clear()

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def read_stream(self, request_id: uuid.UUID, timeout_s: float) -> bytes:
        """Read the first data byte from a stream with a timeout.

        Args:
            request_id: UUID of the stream to read from.
            timeout_s:  Seconds to wait for the first frame before raising.

        Returns:
            The first payload bytes from the stream queue.

        Raises:
            StreamNotFoundError:    When request_id has no registered stream.
            FirstByteTimeoutError:  When no data arrives within timeout_s.
        """
        state = self.get_stream(request_id)
        try:
            return await asyncio.wait_for(state.queue.get(), timeout=timeout_s)
        except asyncio.TimeoutError:
            raise FirstByteTimeoutError(
                f"Stream {request_id} did not produce first byte within {timeout_s}s"
            )

    async def read_stream_iter(
        self, request_id: uuid.UUID
    ):
        """Async generator that yields frames from a stream until it is closed.

        Uses asyncio.wait on queue.get() and stream.closed.wait() so the generator
        exits cleanly when the stream is closed without waiting for the queue to drain.

        Args:
            request_id: UUID of the stream to read from.

        Yields:
            Successive payload bytes from the stream queue.

        Raises:
            StreamNotFoundError: When request_id has no registered stream.
        """
        state = self.get_stream(request_id)
        loop = asyncio.get_event_loop()

        while True:
            get_task = asyncio.ensure_future(state.queue.get())
            closed_task = asyncio.ensure_future(state.closed.wait())

            done, pending = await asyncio.wait(
                {get_task, closed_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if get_task in done:
                yield get_task.result()
                # Check if also closed — drain remaining items
                if state.closed.is_set() and state.queue.empty():
                    self.remove_stream(request_id)
                    return
            else:
                # closed_task completed — drain any remaining queued frames
                while not state.queue.empty():
                    yield state.queue.get_nowait()
                self.remove_stream(request_id)
                return

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Cancel the heartbeat task, close all streams, and close the WebSocket.

        Closing the WebSocket breaks any pending receive() call in the receive
        loop, allowing TTL expiry and clean shutdown to propagate.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._closed:
            return
        self._tear_down("Connection closed by close()")
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        try:
            await self._ws.close()
        except Exception:
            pass
