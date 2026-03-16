# Phase 8: Tunnel Protocol - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

A shared protocol library enables binary-framed, multiplexed communication between relay and agent over a single WebSocket connection. This phase builds the protocol primitives and high-level connection abstraction. Relay server (Phase 9), agent CLI (Phase 10), and remote UI adaptation (Phase 11) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Frame format
- Fixed 21-byte binary header: 1 byte type + 16 bytes UUID request_id + 4 bytes payload_length
- 64 KB max payload per frame — protocol rejects frames larger than 64 KB
- Large files chunked into 64 KB frames at the sender
- Big-endian byte order for multi-byte header fields (network byte order)

### Multiplexing model
- Stream-based lifecycle: open/data/close frames per request
- Full concurrency — multiple streams interleave on the same WebSocket, UUID correlation keeps them separate
- Explicit CANCEL frame when browser disconnects mid-transfer — agent stops streaming and cleans up
- 30-second first-byte timeout — if agent hasn't started responding in 30s, relay returns error to browser; streaming can continue indefinitely once started
- 100 concurrent streams max per agent connection

### Backpressure strategy
- Bounded asyncio.Queue per request stream, 64 frames deep (64 × 64 KB = 4 MB buffer per stream)
- When queue is full, sender blocks (asyncio.Queue.put awaits) — natural flow control, agent slows to match browser consumption speed
- No frame dropping — data integrity preserved
- Fixed 15-second heartbeat interval: relay sends ping, agent responds with pong; 3 missed pings (45s) = connection dead

### Control vs data framing
- Text WebSocket frames for JSON control messages (mount registration, heartbeat, errors)
- Binary WebSocket frames for data with 21-byte header
- Uses WebSocket's native text/binary distinction — no ambiguity, no extra framing

### Library packaging
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

</decisions>

<specifics>
## Specific Ideas

- Header is 21 bytes not 9 bytes because UUID (16 bytes) was chosen over uint32 (4 bytes) for request correlation — globally unique IDs aid debugging across relay logs and agent logs
- Text/binary WebSocket distinction matches TUNL-04 requirement naturally — JSON control messages as text frames are self-describing

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ConnectionManager` in `server/app/services/connection_manager.py`: Manages WebSocket connections with connect/disconnect/broadcast pattern — the relay will need a similar but different manager for agent connections
- `server/app/models/enums.py`: Existing enum patterns (DeviceType) — tunnel frame types should follow the same style

### Established Patterns
- FastAPI WebSocket handling in `server/app/routers/websocket.py`: Existing WS endpoint pattern for LAN features
- `create_app()` factory in `server/app/main.py`: Relay server (Phase 9) will use the same factory pattern
- Cookie-based auth via `itsdangerous` in middleware chain: Remote auth tunneling is Phase 11's concern

### Integration Points
- `tunnel/` module will be imported by relay (Phase 9) and agent (Phase 10)
- Protocol must support tunneling HTTP requests that include cookies (for auth pass-through in Phase 11)
- Stream open frame should carry enough HTTP metadata (method, path, headers) for the agent to reconstruct the request

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-tunnel-protocol*
*Context gathered: 2026-03-11*
