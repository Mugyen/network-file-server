"""Depth tests for TunnelConnection.read_stream_iter and randomized framing.

The iterator is the relay's streaming-response engine: drain-after-close
and cancellation behavior decide whether downloads truncate or hang.
"""

import asyncio
import random
import uuid

import pytest

from tunnel.connection import TunnelConnection
from tunnel.enums import FrameType
from tunnel.exceptions import StreamNotFoundError
from tunnel.frames import deserialize_frame, serialize_frame


class MockWebSocket:
    """Minimal WebSocketProtocol implementation for driving the connection."""

    def __init__(self) -> None:
        self.sent_bytes: list[bytes] = []
        self.sent_text: list[str] = []
        self.closed = False

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    async def receive_bytes(self) -> bytes:
        raise NotImplementedError

    async def receive_text(self) -> str:
        raise NotImplementedError

    async def receive(self) -> dict:
        raise NotImplementedError

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def conn() -> TunnelConnection:
    return TunnelConnection(MockWebSocket())


async def _collect(conn: TunnelConnection, stream_id: uuid.UUID) -> list[bytes]:
    chunks: list[bytes] = []
    async for chunk in conn.read_stream_iter(stream_id):
        chunks.append(chunk)
    return chunks


class TestReadStreamIter:
    async def test_yields_queued_data_then_exits_on_close(self, conn) -> None:
        stream_id = uuid.uuid4()
        conn.open_stream(stream_id)

        await conn._dispatch_frame(FrameType.DATA, stream_id, b"one")
        await conn._dispatch_frame(FrameType.DATA, stream_id, b"two")
        await conn._dispatch_frame(FrameType.CLOSE, stream_id, b"")

        chunks = await asyncio.wait_for(_collect(conn, stream_id), timeout=5)
        assert chunks == [b"one", b"two"]

    async def test_drains_queue_fully_when_close_races_ahead(self, conn) -> None:
        """CLOSE arriving before the consumer starts must not drop the
        queued frames (truncated download otherwise)."""
        stream_id = uuid.uuid4()
        conn.open_stream(stream_id)

        payloads = [bytes([i]) * 100 for i in range(10)]
        for p in payloads:
            await conn._dispatch_frame(FrameType.DATA, stream_id, p)
        await conn._dispatch_frame(FrameType.CLOSE, stream_id, b"")

        chunks = await asyncio.wait_for(_collect(conn, stream_id), timeout=5)
        assert chunks == payloads

    async def test_stream_removed_after_drain(self, conn) -> None:
        stream_id = uuid.uuid4()
        conn.open_stream(stream_id)
        await conn._dispatch_frame(FrameType.DATA, stream_id, b"x")
        await conn._dispatch_frame(FrameType.CLOSE, stream_id, b"")

        await asyncio.wait_for(_collect(conn, stream_id), timeout=5)
        with pytest.raises(StreamNotFoundError):
            conn.get_stream(stream_id)

    async def test_unknown_stream_raises(self, conn) -> None:
        with pytest.raises(StreamNotFoundError):
            async for _ in conn.read_stream_iter(uuid.uuid4()):
                pass  # pragma: no cover

    async def test_consumer_cancellation_leaves_connection_usable(self, conn) -> None:
        """A browser disconnecting mid-stream cancels the iterator; other
        streams must keep working."""
        stream_a = uuid.uuid4()
        stream_b = uuid.uuid4()
        conn.open_stream(stream_a)
        conn.open_stream(stream_b)

        task = asyncio.create_task(_collect(conn, stream_a))
        await asyncio.sleep(0.01)  # let the iterator block on an empty queue
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        await conn._dispatch_frame(FrameType.DATA, stream_b, b"still alive")
        await conn._dispatch_frame(FrameType.CLOSE, stream_b, b"")
        chunks = await asyncio.wait_for(_collect(conn, stream_b), timeout=5)
        assert chunks == [b"still alive"]

    async def test_interleaved_producer_consumer(self, conn) -> None:
        """Producer and consumer running concurrently see every frame in
        order (no drops under the bounded-queue backpressure design)."""
        stream_id = uuid.uuid4()
        conn.open_stream(stream_id)
        payloads = [f"chunk-{i}".encode() for i in range(200)]

        async def produce() -> None:
            for p in payloads:
                await conn._dispatch_frame(FrameType.DATA, stream_id, p)
            await conn._dispatch_frame(FrameType.CLOSE, stream_id, b"")

        producer = asyncio.create_task(produce())
        chunks = await asyncio.wait_for(_collect(conn, stream_id), timeout=10)
        await producer
        assert chunks == payloads


class TestRandomizedFraming:
    def test_random_round_trips(self) -> None:
        """Property-style: random frame type / UUID / payload always
        round-trips byte-identically (seeded for reproducibility)."""
        rng = random.Random(0xF4B1E)
        frame_types = list(FrameType)
        for _ in range(500):
            frame_type = rng.choice(frame_types)
            stream_id = uuid.UUID(int=rng.getrandbits(128))
            payload = rng.randbytes(rng.randint(0, 4096))
            wire = serialize_frame(frame_type, stream_id, payload)
            got_type, got_id, got_payload = deserialize_frame(wire)
            assert (got_type, got_id, got_payload) == (frame_type, stream_id, payload)

    def test_random_corruption_never_misparses_silently(self) -> None:
        """Truncations of a valid frame either raise a tunnel error or (for
        truncated payloads that still satisfy the declared length) cannot
        happen — deserialize validates header vs payload length."""
        from tunnel.exceptions import TunnelError

        rng = random.Random(0xC0FFEE)
        wire = serialize_frame(FrameType.DATA, uuid.uuid4(), b"x" * 256)
        for _ in range(100):
            cut = rng.randint(0, len(wire) - 1)
            truncated = wire[:cut]
            with pytest.raises((TunnelError, ValueError)):
                deserialize_frame(truncated)
