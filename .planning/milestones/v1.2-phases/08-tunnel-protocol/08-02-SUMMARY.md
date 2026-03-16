---
phase: 08-tunnel-protocol
plan: 02
subsystem: infra
tags: [tunnel, websocket, multiplexing, backpressure, heartbeat, asyncio, tdd]

# Dependency graph
requires:
  - 08-01 (tunnel primitives: frames, enums, exceptions, protocol, constants)
provides:
  - TunnelConnection class with UUID-correlated stream multiplexing
  - Per-stream bounded asyncio.Queue backpressure (QUEUE_DEPTH=64)
  - Heartbeat loop with pong-based liveness detection and teardown
  - First-byte timeout via asyncio.wait_for
  - Idempotent close() with heartbeat cancellation and stream cleanup
  - StreamState dataclass (queue + closed Event)
  - Full public API re-exports in tunnel/__init__.py
affects:
  - 09 (relay server uses TunnelConnection to multiplex browser requests)
  - 10 (agent CLI uses TunnelConnection to forward to local HTTP server)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.Queue(maxsize=QUEUE_DEPTH) for per-stream bounded backpressure
    - asyncio.Event for stream lifecycle signalling (closed event)
    - asyncio.wait with FIRST_COMPLETED for drain-safe async generator
    - asyncio.create_task for background heartbeat with cancel-on-close
    - asyncio.wait_for for first-byte timeout with FirstByteTimeoutError
    - task.cancel() + CancelledError suppression for clean heartbeat stop
    - dataclass with field(default_factory=...) for per-instance queue/event

key-files:
  created:
    - tunnel/connection.py
    - tests/tunnel/test_connection.py
  modified:
    - tunnel/__init__.py

key-decisions:
  - "run_receive_loop is an infinite loop — tests use asyncio.create_task + cancel after sleep(0.05) rather than awaiting directly"
  - "start_heartbeat takes heartbeat_interval_s and missed_limit as required parameters (no defaults per project rule) — production callers pass HEARTBEAT_INTERVAL_S and HEARTBEAT_MISSED_LIMIT constants"
  - "_dispatch_frame is synchronous (put_nowait) so tests can verify routing without async; backpressure only manifests in the async put() path"
  - "read_stream_iter uses asyncio.wait(FIRST_COMPLETED) on queue.get() and closed.wait() to avoid blocking on an empty queue after stream close"

# Metrics
duration: 9min
completed: 2026-03-11
---

# Phase 8 Plan 2: TunnelConnection Multiplexing Summary

**TunnelConnection wrapping a WebSocket with UUID-correlated stream multiplexing, per-stream asyncio.Queue backpressure, heartbeat ping/pong lifecycle, and idempotent close**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-03-11T09:13:37Z
- **Completed:** 2026-03-11T09:22:25Z
- **Tasks:** 2 (both TDD with RED/GREEN/REFACTOR)
- **Files modified:** 3 (created 2, modified 1)

## Accomplishments

- `tunnel/connection.py` with `StreamState` dataclass and `TunnelConnection` class (318 lines)
- `StreamState`: `asyncio.Queue(maxsize=64)` for backpressure + `asyncio.Event` for closed signalling
- `TunnelConnection`: `open_stream`, `close_stream`, `get_stream`, `_dispatch_frame`, `send_data`, `send_open`, `send_close`, `send_cancel`, `send_control`, `receive_control`, `run_receive_loop`, `start_heartbeat`, `handle_pong`, `_tear_down`, `read_stream`, `read_stream_iter`, `close`
- Heartbeat loop: sends `{"type": "ping"}` every `heartbeat_interval_s`, awaits `_pong_event` with timeout, tears down after `missed_limit` consecutive misses
- `read_stream_iter`: drain-safe async generator using `asyncio.wait(FIRST_COMPLETED)` on queue.get() and closed.wait()
- 31 comprehensive async tests covering stream lifecycle, multiplexing isolation, send serialization, control message validation, backpressure, heartbeat, first-byte timeout, and teardown
- All 53 tunnel tests + 329 server tests pass (no regressions)

## Task Commits

Task 1 TDD:
1. **RED — failing stream lifecycle tests** — `02b868e` (test)
2. **GREEN + REFACTOR — connection.py implementation** — `b876634` (feat)

Task 2 TDD (tests passed immediately — implementation was already complete from Task 1):
3. **GREEN — backpressure/heartbeat/teardown tests + __init__.py** — `2883cd4` (feat)

## Files Created/Modified

- `tunnel/connection.py` — TunnelConnection with full multiplexing, heartbeat, backpressure (new, 318 lines)
- `tests/tunnel/test_connection.py` — 31 comprehensive async tests for all TunnelConnection behaviors (new, 537 lines)
- `tunnel/__init__.py` — Added TunnelConnection and StreamState to public re-exports (modified)

## Decisions Made

- **Infinite receive loop requires task cancellation in tests**: `run_receive_loop` is a `while True` loop (production pattern) — tests that exercise it use `asyncio.create_task + cancel after sleep(0.05)` to avoid hanging.
- **Synchronous `_dispatch_frame` with `put_nowait`**: The dispatch method is sync so tests can call it directly without async complexity. Backpressure is exercised through the raw queue in dedicated backpressure tests.
- **`start_heartbeat` with required parameters**: Following project rule of no default parameters; callers pass `HEARTBEAT_INTERVAL_S` and `HEARTBEAT_MISSED_LIMIT` explicitly (or test values like `0.05` for fast tests).
- **Task 2 tests immediately GREEN**: All heartbeat/backpressure/teardown methods were implemented holistically in Task 1's GREEN phase. Tests confirmed the implementation was correct without needing a separate fix iteration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Infinite receive loop caused test to hang**
- **Found during:** Task 1 GREEN phase (test run)
- **Issue:** `test_receive_loop_dispatches_binary_frame_to_stream` called `await conn.run_receive_loop()` directly — after processing DATA + CLOSE frames, the loop blocked on the next `ws.receive()` waiting for a frame that never arrived
- **Fix:** Rewrote both receive loop tests to use `asyncio.create_task + sleep(0.05) + cancel` pattern — same pattern documented in the plan's checkpoint references
- **Files modified:** tests/tunnel/test_connection.py
- **Commit:** b876634 (GREEN phase)

---

**Total deviations:** 1 auto-fixed (1 bug in test approach)
**Impact on plan:** Minor test rewrite, no scope creep, implementation unchanged.

## Self-Check

All created files exist:
- [x] tunnel/connection.py — found
- [x] tests/tunnel/test_connection.py — found
- [x] tunnel/__init__.py — modified

All commits exist:
- [x] 02b868e — test RED phase
- [x] b876634 — feat GREEN phase connection.py
- [x] 2883cd4 — feat Task 2 tests + __init__.py

## Self-Check: PASSED

## Next Phase Readiness

- `TunnelConnection` ready for Phase 9 (relay server) and Phase 10 (agent CLI)
- `WebSocketProtocol` adapter pattern established — FastAPI WebSocket wrapping is the next integration step
- All stream lifecycle, multiplexing, and heartbeat behaviors tested and verified
