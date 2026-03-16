---
phase: 08-tunnel-protocol
plan: 01
subsystem: infra
tags: [tunnel, websocket, binary-framing, protocol, struct, uuid, asyncio]

# Dependency graph
requires: []
provides:
  - Binary frame serialize/deserialize with 21-byte header (type + UUID + payload_length)
  - FrameType enum with 7 values (OPEN, DATA, CLOSE, CANCEL, ERROR, PING, PONG)
  - Typed exception hierarchy (TunnelError, FrameTooLargeError, StreamLimitError, FirstByteTimeoutError, StreamNotFoundError)
  - WebSocketProtocol runtime-checkable Protocol interface (framework-agnostic)
  - MockWebSocket test fixture with feed_binary/feed_text helpers
  - Protocol constants (HEADER_SIZE=21, MAX_PAYLOAD_BYTES=65536, etc.)
affects:
  - 08-02 (TunnelConnection multiplexing builds on these primitives)
  - 09 (relay server imports tunnel package)
  - 10 (agent CLI imports tunnel package)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - FrameType(int, Enum) for sequential byte-value frame types
    - struct.pack/unpack with HEADER_FORMAT for deterministic wire encoding
    - typing.Protocol with @runtime_checkable for framework-agnostic interfaces
    - tests/ without __init__.py to avoid shadowing production packages

key-files:
  created:
    - tunnel/__init__.py
    - tunnel/constants.py
    - tunnel/enums.py
    - tunnel/exceptions.py
    - tunnel/frames.py
    - tunnel/protocol.py
    - tests/tunnel/conftest.py
    - tests/tunnel/test_frames.py
  modified:
    - pyproject.toml

key-decisions:
  - "tests/tunnel/ has no __init__.py — prevents tests/ being added to sys.path and shadowing the real tunnel/ package"
  - "FrameType(int, Enum) not (str, Enum) — frame types are single-byte integers on the wire"
  - "deserialize_frame raises ValueError (not TunnelError) for unknown frame type byte — lets FrameType() ValueError propagate naturally"

patterns-established:
  - "Strict types everywhere — no default parameters, no Optional returns, typed exceptions only"
  - "TDD RED-GREEN-REFACTOR — RED commit first, then GREEN, then REFACTOR with public API exports"

requirements-completed:
  - TUNL-01
  - TUNL-04

# Metrics
duration: 3min
completed: 2026-03-11
---

# Phase 8 Plan 1: Tunnel Protocol Primitives Summary

**21-byte binary frame serialization with struct pack/unpack, FrameType(int, Enum), typed exception hierarchy, and runtime-checkable WebSocketProtocol interface**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T09:07:46Z
- **Completed:** 2026-03-11T09:11:00Z
- **Tasks:** 1 (TDD with 3 commits)
- **Files modified:** 9

## Accomplishments

- `tunnel/frames.py` with `serialize_frame`/`deserialize_frame` using `struct.pack/unpack`; big-endian 21-byte header (1B type + 16B UUID + 4B uint32 length)
- 22 TDD tests covering all 7 FrameType values, round-trips, oversized/undersized/mismatch rejection, UUID byte fidelity, and empty payloads
- `WebSocketProtocol` as `@runtime_checkable` Protocol with `send_bytes`, `send_text`, `receive_bytes`, `receive_text`, `receive` — no FastAPI dependency in tunnel module
- `MockWebSocket` fixture with `asyncio.Queue` inbound staging and `feed_binary`/`feed_text` helpers ready for Plan 02

## Task Commits

TDD task committed in three phases:

1. **RED — failing tests + support files** - `eb43824` (test)
2. **GREEN + REFACTOR — frames.py + public API exports** - `307bd76` (feat)

## Files Created/Modified

- `tunnel/__init__.py` - Public API re-exports for all constants, enums, exceptions, functions, protocol
- `tunnel/constants.py` - HEADER_FORMAT, HEADER_SIZE=21, MAX_PAYLOAD_BYTES=65536, and operational constants
- `tunnel/enums.py` - FrameType(int, Enum) with 7 sequential hex values 0x01–0x07
- `tunnel/exceptions.py` - TunnelError base + FrameTooLargeError, StreamLimitError, FirstByteTimeoutError, StreamNotFoundError
- `tunnel/frames.py` - serialize_frame and deserialize_frame with strict validation
- `tunnel/protocol.py` - WebSocketProtocol @runtime_checkable Protocol interface
- `tests/tunnel/conftest.py` - MockWebSocket + mock_ws pytest fixture
- `tests/tunnel/test_frames.py` - 22 exhaustive frame serialization tests
- `pyproject.toml` - testpaths updated to include "tests"; packages updated to include "tunnel"

## Decisions Made

- **No `tests/tunnel/__init__.py`**: When pytest adds `tests/` to `sys.path`, a `tests/tunnel/__init__.py` would shadow the real `tunnel/` package and cause `ModuleNotFoundError` on `tunnel.constants`. Removing it fixes the path shadowing. The `server/tests/__init__.py` has the same convention (empty, but the `server/` prefix prevents shadowing).
- **`FrameType(int, Enum)` not `(str, Enum)`**: Frame types are single-byte integers on the wire; using int allows direct comparison with the unpacked struct byte without conversion.
- **`ValueError` for unknown frame type**: `deserialize_frame` lets `FrameType(type_byte)` raise `ValueError` naturally rather than catching and re-raising as `TunnelError`. This is the expected Python enum behavior for invalid values.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed tests/tunnel/__init__.py to fix package shadowing**
- **Found during:** Task 1 RED phase (test collection)
- **Issue:** Plan specified creating `tests/tunnel/__init__.py`; this caused pytest to add `tests/` to `sys.path`, making `import tunnel.constants` find the empty `tests/tunnel/` package instead of the real `tunnel/` package
- **Fix:** Removed `tests/tunnel/__init__.py`; test discovery still works correctly via pytest's rootdir-based collection
- **Files modified:** tests/tunnel/__init__.py (deleted)
- **Verification:** `uv run pytest tests/tunnel/test_frames.py -x -v` — 22 passed
- **Committed in:** eb43824 (RED phase commit — file not staged)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required fix for test collection to work. No scope creep.

## Issues Encountered

- pytest `sys.path` manipulation caused `tests/tunnel/` to shadow `tunnel/` when `__init__.py` was present in the test subdirectory. Resolved by removing the `__init__.py` (standard pytest pattern for non-package test directories).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All tunnel primitives ready for Plan 02 (TunnelConnection multiplexing)
- `MockWebSocket` available in `tests/tunnel/conftest.py` for Plan 02 stream tests
- `WebSocketProtocol` interface defined — relay (Phase 9) and agent (Phase 10) will wrap FastAPI WebSocket in an adapter

---
*Phase: 08-tunnel-protocol*
*Completed: 2026-03-11*
