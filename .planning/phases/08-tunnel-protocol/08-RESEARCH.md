# Phase 08: Tunnel Protocol - Research

**Researched:** 2026-03-11
**Domain:** Binary WebSocket framing, asyncio multiplexing, Python Protocol/ABC patterns
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Frame format:**
- Fixed 21-byte binary header: 1 byte type + 16 bytes UUID request_id + 4 bytes payload_length
- 64 KB max payload per frame — protocol rejects frames larger than 64 KB
- Large files chunked into 64 KB frames at the sender
- Big-endian byte order for multi-byte header fields (network byte order)

**Multiplexing model:**
- Stream-based lifecycle: open/data/close frames per request
- Full concurrency — multiple streams interleave on the same WebSocket, UUID correlation keeps them separate
- Explicit CANCEL frame when browser disconnects mid-transfer — agent stops streaming and cleans up
- 30-second first-byte timeout — if agent hasn't started responding in 30s, relay returns error to browser; streaming can continue indefinitely once started
- 100 concurrent streams max per agent connection

**Backpressure strategy:**
- Bounded asyncio.Queue per request stream, 64 frames deep (64 x 64 KB = 4 MB buffer per stream)
- When queue is full, sender blocks (asyncio.Queue.put awaits) — natural flow control
- No frame dropping — data integrity preserved
- Fixed 15-second heartbeat interval: relay sends ping, agent responds with pong; 3 missed pings (45s) = connection dead

**Control vs data framing:**
- Text WebSocket frames for JSON control messages (mount registration, heartbeat, errors)
- Binary WebSocket frames for data with 21-byte header
- Uses WebSocket's native text/binary distinction — no ambiguity, no extra framing

**Library packaging:**
- Shared `tunnel/` top-level directory in monorepo alongside `server/` and `client/`
- Both high-level and low-level APIs:
  - Low-level: frame serialization/deserialization, frame type enum, constants
  - High-level: `TunnelConnection` class wrapping a WebSocket with multiplexing, heartbeat, and backpressure
- Framework-agnostic: uses Protocol/ABC for WebSocket interface (send_bytes, receive_bytes); relay and agent provide FastAPI WebSocket adapters
- Testable in isolation with mock WebSocket — no FastAPI dependency in tunnel module

### Claude's Discretion
- Exact frame type enum values and naming
- Internal data structures for stream tracking
- Error frame payload format
- Test strategy and mock WebSocket implementation details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TUNL-01 | Agent and relay communicate via binary WebSocket frames with 9-byte headers (type, request_id, payload_length) | Note: CONTEXT.md locks header at 21 bytes (UUID is 16 bytes, not uint32). `struct` stdlib handles this exactly. |
| TUNL-02 | Concurrent browser requests are multiplexed over a single agent WebSocket using correlation IDs | `asyncio.Queue` per stream + UUID correlation via `uuid.uuid4()`. Stream state tracked in a dict keyed by UUID. |
| TUNL-03 | Relay enforces backpressure via bounded asyncio.Queue to prevent OOM during large transfers | `asyncio.Queue(maxsize=64)` blocks naturally when full — verified stdlib behavior. |
| TUNL-04 | Control messages (mount registration, heartbeat, errors) use JSON text frames | WebSocket text/binary distinction maps directly. FastAPI exposes `receive_text()` / `send_text()` and `receive_bytes()` / `send_bytes()` separately. |
</phase_requirements>

## Summary

Phase 8 builds a self-contained `tunnel/` Python package providing binary WebSocket framing and async stream multiplexing. Everything required is in the Python standard library (`struct`, `uuid`, `asyncio`, `typing.Protocol`, `json`, `dataclasses`) plus FastAPI/Starlette's existing WebSocket support — no new dependencies needed.

The core design is three layers: (1) raw frame serialization using `struct.pack`/`struct.unpack` with a 21-byte header (`>B16sI`), (2) a stream tracking layer using `dict[uuid.UUID, asyncio.Queue[bytes]]` with per-stream bounded queues, and (3) `TunnelConnection` — a high-level class that drives the send/receive loop, dispatches frames to queues, and manages heartbeat via `asyncio.create_task`. The `WebSocketProtocol` typing.Protocol interface makes the class testable with pure mock objects and FastAPI-compatible via a thin adapter.

The existing project already uses `AsyncMock` for WebSocket unit tests (see `test_websocket.py`) and `asyncio_mode = "auto"` in pytest — the test infrastructure for this new module requires zero new tooling.

**Primary recommendation:** Implement `tunnel/` as a pure Python package with no new third-party dependencies. Use `struct.pack('>B16sI', ...)` for the 21-byte header, `asyncio.Queue(maxsize=64)` for per-stream backpressure, and `typing.Protocol` for the WebSocket abstraction.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `struct` | stdlib | Binary header pack/unpack | Only correct way to produce deterministic binary layouts in Python |
| `uuid` | stdlib | UUID generation and bytes serialization | `uuid.uuid4()` gives globally unique 16-byte IDs; `.bytes` property gives big-endian bytes directly |
| `asyncio` | stdlib | Event loop, `Queue`, `Task`, `wait_for`, `Event` | Required for concurrent stream handling on a single WebSocket |
| `typing` | stdlib | `Protocol`, `TypeAlias`, `runtime_checkable` | Framework-agnostic WebSocket interface without importing FastAPI |
| `json` | stdlib | Control message serialization | JSON text frames for control messages (TUNL-04) |
| `dataclasses` | stdlib | Frame and stream state data structures | Matches existing project pattern (see `DeviceInfo` in connection_manager.py) |
| `enum` | stdlib | `FrameType` enum with int values | Matches existing project pattern (see `enums.py`) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI WebSocket | already in project | Adapts to `WebSocketProtocol` in relay/agent | Phase 9 and 10 will wrap `fastapi.WebSocket` with a thin adapter |
| `pytest-asyncio` | already in dev deps | Async test support | All tunnel tests are async; `asyncio_mode = "auto"` already configured |
| `unittest.mock.AsyncMock` | stdlib | Mock WebSocket for unit tests | Matches existing test style in `test_websocket.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `struct` | `construct` / `bitstruct` | Third-party libs add dependency; `struct` handles this fixed format perfectly |
| `uuid.UUID` as dict key | string UUID | UUID objects are hashable and avoid repeated string parsing; strings are fine but wasteful |
| `typing.Protocol` | `abc.ABC` | Protocol is structurally typed (duck typing); ABC requires explicit inheritance — Protocol is better for adapter pattern |

**Installation:** No new packages required. All dependencies already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
tunnel/
├── __init__.py          # Re-exports public API: FrameType, TunnelFrame, TunnelConnection, WebSocketProtocol
├── constants.py         # MAX_PAYLOAD_BYTES, HEADER_SIZE, HEADER_FORMAT, MAX_STREAMS, HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT, FIRST_BYTE_TIMEOUT_S, QUEUE_DEPTH
├── enums.py             # FrameType(int, Enum): OPEN, DATA, CLOSE, CANCEL, ERROR, PING, PONG
├── frames.py            # TunnelFrame dataclass + serialize() / deserialize() functions
├── connection.py        # TunnelConnection class: multiplexing, heartbeat, stream lifecycle
└── exceptions.py        # TunnelError, FrameTooLargeError, StreamLimitError, FirstByteTimeoutError, StreamNotFoundError

tests/tunnel/
├── __init__.py
├── test_frames.py       # serialize/deserialize round-trips, edge cases, invalid input
├── test_connection.py   # multiplexing, backpressure, heartbeat, cancel, timeout
└── conftest.py          # MockWebSocket, helpers
```

### Pattern 1: Fixed-Format Binary Header with `struct`
**What:** Pack/unpack a 21-byte header using big-endian format string.
**When to use:** Every frame serialization and deserialization call.
**Example:**
```python
# Source: Python stdlib struct documentation
import struct
import uuid
from tunnel.enums import FrameType

HEADER_FORMAT = ">B16sI"   # big-endian: 1B type, 16B UUID bytes, 4B uint32 length
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # == 21

def serialize_frame(frame_type: FrameType, request_id: uuid.UUID, payload: bytes) -> bytes:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise FrameTooLargeError(f"Payload {len(payload)} exceeds {MAX_PAYLOAD_BYTES}")
    header = struct.pack(HEADER_FORMAT, frame_type.value, request_id.bytes, len(payload))
    return header + payload

def deserialize_header(data: bytes) -> tuple[FrameType, uuid.UUID, int]:
    if len(data) < HEADER_SIZE:
        raise TunnelError(f"Header too short: {len(data)} < {HEADER_SIZE}")
    raw_type, uuid_bytes, payload_length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return FrameType(raw_type), uuid.UUID(bytes=uuid_bytes), payload_length
```

### Pattern 2: `typing.Protocol` WebSocket Abstraction
**What:** Define a structural interface so `TunnelConnection` works with FastAPI WebSocket and mock objects equally.
**When to use:** Parameterize `TunnelConnection.__init__` with this type — never import `fastapi.WebSocket` in the tunnel module.
**Example:**
```python
# Source: Python typing.Protocol docs
from typing import Protocol, runtime_checkable

@runtime_checkable
class WebSocketProtocol(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_text(self, data: str) -> None: ...
    async def receive_bytes(self) -> bytes: ...
    async def receive_text(self) -> str: ...
```

Note: FastAPI's `WebSocket` exposes `send_bytes`, `send_text`, `receive_bytes`, `receive_text` natively. The adapter for relay/agent phases is zero-code — pass the `WebSocket` directly.

### Pattern 3: Per-Stream asyncio.Queue for Backpressure
**What:** Each open stream gets a `Queue(maxsize=64)`. The receive dispatch loop puts frames in; the consumer awaits get().
**When to use:** The receive loop dispatches every DATA frame to the correct stream's queue. Backpressure is automatic: when queue is full, `await queue.put(payload)` blocks, which blocks the WebSocket receive loop, which blocks TCP reads — propagating back-pressure to the sender.
**Example:**
```python
import asyncio
import uuid
from dataclasses import dataclass, field

QUEUE_DEPTH = 64

@dataclass
class StreamState:
    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=QUEUE_DEPTH))
    closed: asyncio.Event = field(default_factory=asyncio.Event)

class TunnelConnection:
    def __init__(self, ws: WebSocketProtocol) -> None:
        self._ws = ws
        self._streams: dict[uuid.UUID, StreamState] = {}

    def _get_stream(self, request_id: uuid.UUID) -> StreamState:
        if request_id not in self._streams:
            raise StreamNotFoundError(f"No stream for {request_id}")
        return self._streams[request_id]

    async def _dispatch_frame(self, frame_type: FrameType, request_id: uuid.UUID, payload: bytes) -> None:
        stream = self._get_stream(request_id)
        if frame_type == FrameType.DATA:
            await stream.queue.put(payload)   # blocks when queue full = backpressure
        elif frame_type in (FrameType.CLOSE, FrameType.CANCEL, FrameType.ERROR):
            stream.closed.set()
```

### Pattern 4: Heartbeat via `asyncio.create_task`
**What:** Relay sends PING every 15 seconds via a background task; tracks consecutive missed pongs; tears down on 3 misses.
**When to use:** Start the heartbeat task when `TunnelConnection` starts its receive loop.
**Example:**
```python
import asyncio

HEARTBEAT_INTERVAL_S = 15
HEARTBEAT_MISSED_LIMIT = 3

async def _heartbeat_loop(self) -> None:
    missed = 0
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)
        await self._send_control({"type": "ping"})
        try:
            await asyncio.wait_for(self._pong_event.wait(), timeout=HEARTBEAT_INTERVAL_S)
            self._pong_event.clear()
            missed = 0
        except asyncio.TimeoutError:
            missed += 1
            if missed >= HEARTBEAT_MISSED_LIMIT:
                await self._tear_down(reason="heartbeat timeout")
                return
```

### Pattern 5: First-Byte Timeout with `asyncio.wait_for`
**What:** When relay opens a stream, it awaits the first DATA frame with a 30-second timeout before returning an error to the browser.
**When to use:** Relay side only, in the stream open handler.
**Example:**
```python
FIRST_BYTE_TIMEOUT_S = 30

async def read_first_byte(self, request_id: uuid.UUID) -> bytes:
    stream = self._get_stream(request_id)
    try:
        return await asyncio.wait_for(stream.queue.get(), timeout=FIRST_BYTE_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise FirstByteTimeoutError(f"No response from agent within {FIRST_BYTE_TIMEOUT_S}s")
```

### Pattern 6: Control Messages as JSON Text Frames
**What:** Mount registration, heartbeat ping/pong, and errors are JSON dicts sent as WebSocket text frames.
**When to use:** Any non-data communication on the tunnel.
**Example:**
```python
import json

async def _send_control(self, message: dict) -> None:
    """Send a JSON text frame. Validates message has a 'type' key."""
    if "type" not in message:
        raise TunnelError("Control message must have a 'type' key")
    await self._ws.send_text(json.dumps(message))

async def _receive_control(self) -> dict:
    raw = await self._ws.receive_text()
    data = json.loads(raw)
    if "type" not in data:
        raise TunnelError("Received control message missing 'type' key")
    return data
```

### Anti-Patterns to Avoid
- **Mixing text and binary dispatch in a single receive loop:** FastAPI WebSocket `receive()` returns a `WebSocketData` dict with either `text` or `bytes` key. Do NOT call `receive_bytes()` when a text frame arrives — it will block or raise. Use `receive()` and check the key, OR have separate tasks for control and data if the transport supports it. Since the tunnel uses native WS text/binary distinction, structure the receive loop to check frame type (text vs binary) before routing.
- **Using `asyncio.Queue.put_nowait()` for backpressure:** `put_nowait` raises `QueueFull` instead of blocking. Always use `await queue.put()` to get the blocking backpressure behavior.
- **Storing stream state after CLOSE/CANCEL without cleanup:** Leaked stream entries in `_streams` dict would accumulate. Always `del self._streams[request_id]` after a stream closes.
- **Importing FastAPI in the `tunnel/` module:** Breaks the framework-agnostic contract. Use only `WebSocketProtocol` in tunnel — relay/agent code provides the adapter.
- **Using `int` enum for FrameType without inheriting `int`:** `FrameType(int, Enum)` allows direct comparison with the raw byte value from `struct.unpack`. Pure `Enum` requires `.value` lookups everywhere.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Binary packing | Custom bit manipulation | `struct.pack`/`struct.unpack` | Handles endianness, alignment, error reporting correctly |
| UUID generation | Random bytes + manual formatting | `uuid.uuid4()` | RFC 4122 compliance, correct entropy, `.bytes` property for 16-byte wire format |
| Bounded queue backpressure | Custom semaphore + list | `asyncio.Queue(maxsize=N)` | Atomic enqueue/block, integrates with event loop correctly, QueueFull for non-blocking paths |
| Task cancellation on timeout | Manual flag polling | `asyncio.wait_for(..., timeout=N)` + `asyncio.TimeoutError` | Correct cooperative cancellation with the event loop |
| Text/binary frame distinction | Length prefix or magic bytes | WebSocket native text/binary frames | Already part of the WebSocket protocol; FastAPI exposes it directly |

**Key insight:** The Python standard library covers 100% of the low-level protocol mechanics. The implementation complexity is in the stream lifecycle state machine, not the framing itself.

## Common Pitfalls

### Pitfall 1: FastAPI WebSocket receive_bytes() vs receive()
**What goes wrong:** Calling `await websocket.receive_bytes()` when the next frame is a text frame raises a WebSocket protocol error or hangs.
**Why it happens:** FastAPI's WebSocket has type-specific receive methods. If the sender sends a text frame (control message) and the receiver is blocking on `receive_bytes()`, the frame is misrouted.
**How to avoid:** In the TunnelConnection receive loop, use `await websocket.receive()` to get the raw `WebSocketData` dict, then branch on `"text"` vs `"bytes"` key. OR structure protocol so control messages only arrive at known protocol points (handshake, not interleaved).
**Warning signs:** `WebSocketDisconnect` or silent hang in the receive loop when control frames are expected.

### Pitfall 2: asyncio.Queue get() after stream closed
**What goes wrong:** Consumer awaits `queue.get()` forever when the stream is CLOSED before any data arrives (e.g., empty response).
**Why it happens:** CLOSE frame arrives, `closed.set()` fires, but consumer is already blocked on `queue.get()`.
**How to avoid:** Use `asyncio.wait` with both `queue.get()` as a coroutine and `stream.closed.wait()` as a coroutine, with `return_when=FIRST_COMPLETED`. Alternatively, put a sentinel value (e.g., `None`) in the queue when CLOSE arrives — but this requires careful sentinel handling. The `asyncio.wait` approach is cleaner.
**Warning signs:** Relay hangs indefinitely proxying a response after the agent sends an empty body.

### Pitfall 3: Stream limit not enforced before creating queue
**What goes wrong:** Memory exhaustion when > 100 concurrent streams are opened.
**Why it happens:** Each stream allocates up to 4 MB of queue space. 100 streams = 400 MB. Without enforcement, a misbehaving agent could open thousands.
**How to avoid:** Enforce `if len(self._streams) >= MAX_STREAMS: raise StreamLimitError(...)` in the OPEN frame handler before allocating the `StreamState`.
**Warning signs:** Memory usage growing unbounded during load testing.

### Pitfall 4: UUID key mismatch between bytes and object
**What goes wrong:** `uuid.UUID(bytes=uuid_bytes)` and `uuid.UUID("some-string")` compare equal only if they represent the same UUID, but dict lookup fails silently if keys are mixed types (str vs UUID object).
**Why it happens:** Inconsistency in how request_id is stored vs. looked up.
**How to avoid:** Always use `uuid.UUID` objects (not strings) as dict keys throughout the tunnel module. The `deserialize_header()` function must always return a `uuid.UUID` object, never a string.
**Warning signs:** `StreamNotFoundError` raised for a stream that was opened — the UUID exists in the dict but lookup fails due to key type mismatch.

### Pitfall 5: Heartbeat task not cancelled on connection close
**What goes wrong:** `asyncio.Task` for heartbeat continues running after `TunnelConnection` is garbage collected or closed, causing "Task was destroyed but it is pending" warnings or spurious send attempts.
**Why it happens:** `asyncio.create_task()` returns a task that runs until completion or explicit cancellation.
**How to avoid:** Store the heartbeat task and call `task.cancel()` in the teardown/close path. Wrap in try/except `asyncio.CancelledError` in the task itself.
**Warning signs:** "Task was destroyed but it is pending!" log warnings in tests.

## Code Examples

Verified patterns from stdlib documentation and local verification:

### Header Serialization Round-Trip
```python
# Verified locally: struct.calcsize('>B16sI') == 21
import struct
import uuid
from tunnel.enums import FrameType

HEADER_FORMAT = ">B16sI"
HEADER_SIZE = 21  # struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD_BYTES = 65536  # 64 KB

def serialize_frame(frame_type: FrameType, request_id: uuid.UUID, payload: bytes) -> bytes:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise FrameTooLargeError(f"Payload {len(payload)} exceeds {MAX_PAYLOAD_BYTES}")
    header = struct.pack(HEADER_FORMAT, frame_type.value, request_id.bytes, len(payload))
    return header + payload

def deserialize_frame(data: bytes) -> tuple[FrameType, uuid.UUID, bytes]:
    if len(data) < HEADER_SIZE:
        raise TunnelError(f"Frame too short: {len(data)}")
    raw_type, uuid_bytes, payload_length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    payload = data[HEADER_SIZE:HEADER_SIZE + payload_length]
    if len(payload) != payload_length:
        raise TunnelError(f"Payload length mismatch: expected {payload_length}, got {len(payload)}")
    return FrameType(raw_type), uuid.UUID(bytes=uuid_bytes), payload
```

### FrameType Enum (Claude's discretion - recommended values)
```python
from enum import Enum

class FrameType(int, Enum):
    """Binary frame type byte values for the tunnel protocol."""
    OPEN = 0x01    # Start of a new request stream; payload is HTTP metadata JSON
    DATA = 0x02    # Request/response body chunk; payload is raw bytes
    CLOSE = 0x03   # Clean end of stream; payload is empty
    CANCEL = 0x04  # Abort mid-transfer (browser disconnected); payload is empty
    ERROR = 0x05   # Protocol or application error; payload is JSON error info
    PING = 0x06    # Heartbeat probe (relay to agent); payload is empty
    PONG = 0x07    # Heartbeat response (agent to relay); payload is empty
```

### Mock WebSocket for Unit Tests
```python
# Matches existing project pattern: AsyncMock from unittest.mock
import asyncio
import json
from unittest.mock import AsyncMock

class MockWebSocket:
    """Minimal mock WebSocket for TunnelConnection unit tests.

    Feeds pre-programmed binary/text frames via queues.
    Captures sent frames for assertion.
    """
    def __init__(self) -> None:
        self._inbound_binary: asyncio.Queue[bytes] = asyncio.Queue()
        self._inbound_text: asyncio.Queue[str] = asyncio.Queue()
        self.sent_bytes: list[bytes] = []
        self.sent_text: list[str] = []

    async def receive_bytes(self) -> bytes:
        return await self._inbound_binary.get()

    async def receive_text(self) -> str:
        return await self._inbound_text.get()

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def send_text(self, data: str) -> None:
        self.sent_text.append(data)

    def feed_binary(self, data: bytes) -> None:
        self._inbound_binary.put_nowait(data)

    def feed_text(self, data: str) -> None:
        self._inbound_text.put_nowait(data)
```

Note: The actual `TunnelConnection` receive loop needs to handle the interleaving of text and binary frames. One clean approach is a single `receive()` call (using the underlying WebSocket's generic receive) rather than separate `receive_bytes`/`receive_text` calls. The `MockWebSocket` above should be adjusted based on the chosen receive loop design.

### Stream Lifecycle State Machine
```python
# State transitions:
# OPEN frame received  -> create StreamState, add to _streams
# DATA frame received  -> await stream.queue.put(payload)  [blocks on backpressure]
# CLOSE frame received -> stream.closed.set(), del _streams[request_id]
# CANCEL frame received-> stream.closed.set(), del _streams[request_id]
# ERROR frame received -> stream.closed.set(), del _streams[request_id]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom length-prefix framing | Native WebSocket text/binary distinction | WebSocket RFC 6455 (2011) | No extra framing layer needed for control vs data |
| `threading.Queue` for concurrency | `asyncio.Queue` | Python 3.4+ | Single-threaded async; no lock contention |
| String UUIDs for correlation | `uuid.UUID` objects with `.bytes` property | Python 3.0+ | 16-byte wire format; hashable dict keys |
| ABC for interface contracts | `typing.Protocol` (structural subtyping) | Python 3.8+ | No inheritance required; works with existing types |

**Deprecated/outdated:**
- `asyncio.coroutine` / `yield from`: replaced by `async/await` — this codebase already uses `async/await` throughout.
- `asyncio.ensure_future()`: replaced by `asyncio.create_task()` (Python 3.7+) — use `create_task`.

## Open Questions

1. **Receive loop design: single `receive()` vs separate `receive_bytes()`/`receive_text()` calls**
   - What we know: FastAPI's `WebSocket.receive()` returns `{"type": "websocket.receive", "bytes": ..., "text": None}` or with `text` populated. The type-specific methods (`receive_bytes`, `receive_text`) check the key and raise if the frame type doesn't match.
   - What's unclear: Whether to use a single `receive()` and branch, or use two concurrent tasks — one for text frames (control), one for binary frames (data).
   - Recommendation: Single `receive()` in one loop, branch on whether `bytes` or `text` is populated. Simpler, no task coordination needed. The `MockWebSocket` should implement a unified `receive()` method accordingly.

2. **OPEN frame payload format (HTTP metadata for pass-through)**
   - What we know: CONTEXT.md says "stream open frame should carry enough HTTP metadata (method, path, headers) for the agent to reconstruct the request."
   - What's unclear: Exact JSON schema — this is Claude's discretion territory.
   - Recommendation: `{"method": "GET", "path": "/api/files", "headers": {"Cookie": "session=...", "Accept": "*/*"}, "query": "path=subdir"}` as the OPEN frame payload. Simple flat structure, easy to validate.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest server/tests/ tests/tunnel/ -x -q` |
| Full suite command | `uv run pytest server/tests/ tests/tunnel/ -v` |

Note: The `testpaths` in `pyproject.toml` currently only lists `server/tests`. This must be updated to include `tests/tunnel/` (or the tunnel tests placed within `server/tests/`). See Wave 0 gaps.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TUNL-01 | serialize_frame / deserialize_frame round-trip for all FrameType values | unit | `uv run pytest tests/tunnel/test_frames.py -x` | Wave 0 |
| TUNL-01 | deserialize rejects frames shorter than HEADER_SIZE | unit | `uv run pytest tests/tunnel/test_frames.py::test_deserialize_too_short -x` | Wave 0 |
| TUNL-01 | deserialize rejects payload_length > MAX_PAYLOAD_BYTES | unit | `uv run pytest tests/tunnel/test_frames.py::test_serialize_rejects_oversized -x` | Wave 0 |
| TUNL-02 | Two concurrent streams via MockWebSocket receive correct payloads | unit | `uv run pytest tests/tunnel/test_connection.py::test_concurrent_streams -x` | Wave 0 |
| TUNL-02 | CANCEL frame causes StreamNotFoundError or closed event for the correct stream only | unit | `uv run pytest tests/tunnel/test_connection.py::test_cancel_closes_correct_stream -x` | Wave 0 |
| TUNL-02 | Exceeding MAX_STREAMS raises StreamLimitError | unit | `uv run pytest tests/tunnel/test_connection.py::test_stream_limit -x` | Wave 0 |
| TUNL-03 | Queue blocks sender when full (backpressure verified via asyncio timing) | unit | `uv run pytest tests/tunnel/test_connection.py::test_backpressure_blocks -x` | Wave 0 |
| TUNL-03 | No frames dropped when queue is exactly full | unit | `uv run pytest tests/tunnel/test_connection.py::test_no_frame_drop -x` | Wave 0 |
| TUNL-04 | Control messages sent as text frames (verified via MockWebSocket.sent_text) | unit | `uv run pytest tests/tunnel/test_connection.py::test_control_messages_are_text -x` | Wave 0 |
| TUNL-04 | Data frames sent as binary frames (verified via MockWebSocket.sent_bytes) | unit | `uv run pytest tests/tunnel/test_frames.py::test_data_frames_are_binary -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/tunnel/ -x -q`
- **Per wave merge:** `uv run pytest server/tests/ tests/tunnel/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/tunnel/__init__.py` — empty, makes directory a package
- [ ] `tests/tunnel/conftest.py` — `MockWebSocket` fixture and shared test helpers
- [ ] `tests/tunnel/test_frames.py` — covers TUNL-01 (serialization)
- [ ] `tests/tunnel/test_connection.py` — covers TUNL-02, TUNL-03, TUNL-04
- [ ] Update `pyproject.toml` `testpaths` to include `tests/tunnel` OR relocate to `server/tests/tunnel/`
- [ ] `tunnel/__init__.py` — public API re-exports
- [ ] `tunnel/constants.py` — all protocol constants
- [ ] `tunnel/enums.py` — FrameType enum
- [ ] `tunnel/frames.py` — serialize/deserialize functions
- [ ] `tunnel/connection.py` — TunnelConnection class
- [ ] `tunnel/exceptions.py` — typed exception hierarchy

## Sources

### Primary (HIGH confidence)
- Python stdlib `struct` module — format string `>B16sI` verified locally to produce 21 bytes
- Python stdlib `asyncio.Queue` — bounded queue blocking behavior verified locally (`put_nowait` raises `QueueFull`, `await put()` blocks)
- Python stdlib `typing.Protocol` — structural subtyping pattern verified locally
- Python stdlib `uuid` — `uuid.uuid4().bytes` gives 16-byte big-endian representation
- Existing `server/app/models/enums.py` — `(int, Enum)` and `(str, Enum)` patterns used in project
- Existing `server/tests/test_websocket.py` — `AsyncMock` pattern for WebSocket mocking in this project
- Existing `server/tests/conftest.py` — test fixture patterns

### Secondary (MEDIUM confidence)
- FastAPI WebSocket documentation — `send_bytes`, `receive_bytes`, `send_text`, `receive_text` methods confirmed to match `WebSocketProtocol` interface
- `.planning/phases/08-tunnel-protocol/08-CONTEXT.md` — authoritative source for all locked decisions in this phase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib, no new deps, verified with local Python execution
- Architecture: HIGH — derived directly from locked decisions in CONTEXT.md + verified stdlib capabilities
- Pitfalls: HIGH — derived from asyncio semantics and FastAPI WebSocket internals, verified against existing codebase patterns
- Test infrastructure: HIGH — pytest-asyncio already configured, AsyncMock already used in project

**Research date:** 2026-03-11
**Valid until:** 2026-09-11 (stable stdlib — effectively permanent)
