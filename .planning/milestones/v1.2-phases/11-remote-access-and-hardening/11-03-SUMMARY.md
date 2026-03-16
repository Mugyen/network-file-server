---
phase: 11-remote-access-and-hardening
plan: "03"
subsystem: tunnel
tags: [websocket, tunnel, relay, agent, httpx-ws, real-time]

# Dependency graph
requires:
  - phase: 11-01
    provides: agent connect_and_serve, TunnelConnection, relay mount_proxy
  - phase: 10-02
    provides: agent/proxy.py handle_open_frame pattern, _agent_receive_loop_with_metadata
provides:
  - WS_OPEN (0x08), WS_DATA (0x09), WS_CLOSE (0x0A) FrameType values
  - TunnelConnection.send_ws_open/send_ws_data/send_ws_close methods
  - Relay WebSocket proxy endpoint at /m/{code}/{path:path}
  - Agent handle_ws_open_frame for bidirectional local WS bridging
  - httpx-ws promoted to production dependency
affects: [real-time features, clipboard sync, transfer notifications, device discovery]

# Tech tracking
tech-stack:
  added: [httpx-ws promoted to production deps (was dev-only)]
  patterns:
    - WS frame types reuse same stream infrastructure as HTTP (queue + close event)
    - agent_to_browser and browser_to_agent tasks use asyncio.wait(FIRST_COMPLETED) with cancel in finally
    - ASGIWebSocketTransport used as async context manager for in-process WS testing

key-files:
  created: []
  modified:
    - tunnel/enums.py
    - tunnel/connection.py
    - relay/app/routers/mount_proxy.py
    - agent/proxy.py
    - agent/connection.py
    - pyproject.toml
    - tests/tunnel/test_frames.py
    - tests/relay/test_mount_proxy.py
    - tests/agent/test_agent_connection.py
    - tests/agent/test_proxy.py

key-decisions:
  - "WS_DATA dispatches to stream queue (same as DATA); WS_CLOSE closes stream (same as CLOSE) — reuses existing TunnelConnection infrastructure"
  - "handle_ws_open_frame accepts ASGI app directly (not base_url string) — allows ASGIWebSocketTransport to work in-process without real network"
  - "_agent_receive_loop_with_metadata signature extended with app: object parameter — callers (connect_and_serve) pass the ASGI app"
  - "ASGIWebSocketTransport must be used as async context manager (has _task_group via __aenter__); WS tests wrap with async with"
  - "MockWSConnection.read_stream_iter uses asyncio.Queue with None sentinel — prevents agent_to_browser task from completing before browser_to_agent processes messages"
  - "asyncio.sleep(0.05) in WS forwarding test allows relay browser_to_agent task to process queued message before WS disconnect"

patterns-established:
  - "WS bridge pattern: relay sends WS_OPEN → agent opens local WS → two pump tasks (relay_to_local, local_to_relay) with asyncio.wait(FIRST_COMPLETED)"
  - "WS_CLOSE always sent in finally block with try/except swallow — ensures cleanup even if tunnel already closed"

requirements-completed:
  - RMUI-02

# Metrics
duration: 9min
completed: 2026-03-11
---

# Phase 11 Plan 03: WebSocket Tunneling Summary

**WebSocket tunneling via WS_OPEN/WS_DATA/WS_CLOSE frames bridging browser connections through relay tunnel to agent's local ASGI app**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-11T15:10:00Z
- **Completed:** 2026-03-11T15:20:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added WS_OPEN (0x08), WS_DATA (0x09), WS_CLOSE (0x0A) to FrameType enum and supporting TunnelConnection methods
- Relay WebSocket endpoint `/m/{code}/{path:path}` bridges browser WS to tunnel stream with full cleanup on disconnect
- Agent `handle_ws_open_frame` opens local WS to ASGI app via httpx-ws and bridges bidirectionally; promoted httpx-ws to production dependency
- All real-time features (clipboard sync, transfer notifications, device discovery) now work through relay tunnel

## Task Commits

Each task was committed atomically (with TDD red/green commits):

1. **Task 1: TDD RED** - `6d35b29` (test: failing tests for WS frames and relay WS endpoint)
2. **Task 1: TDD GREEN** - `ba8e4a5` (feat: WS frame types, TunnelConnection WS methods, relay WS endpoint)
3. **Task 2: TDD RED** - `4fe22de` (test: failing tests for agent WS_OPEN handler and local WS bridge)
4. **Task 2: TDD GREEN** - `49c38c4` (feat: agent WS_OPEN handler and local WebSocket bridge)

## Files Created/Modified

- `tunnel/enums.py` - Added WS_OPEN, WS_DATA, WS_CLOSE FrameType values
- `tunnel/connection.py` - Added send_ws_open/data/close methods; _dispatch_frame handles WS_DATA/WS_CLOSE
- `relay/app/routers/mount_proxy.py` - Added proxy_websocket endpoint with bidirectional bridging and cleanup
- `agent/proxy.py` - Added handle_ws_open_frame with ASGIWebSocketTransport local WS bridge
- `agent/connection.py` - Updated _agent_receive_loop_with_metadata to dispatch WS_OPEN frames; accepts app parameter
- `pyproject.toml` - Promoted httpx-ws to production dependencies
- `tests/tunnel/test_frames.py` - Added WS frame type round-trip tests
- `tests/relay/test_mount_proxy.py` - Added relay WS endpoint tests (upgrade, WS_OPEN, WS_CLOSE, forwarding)
- `tests/agent/test_agent_connection.py` - Added WS_OPEN dispatch test
- `tests/agent/test_proxy.py` - Added handle_ws_open_frame bridge, cleanup, and query string tests

## Decisions Made

- WS frame types reuse existing stream queue infrastructure: WS_DATA routes to queue, WS_CLOSE signals stream close
- `handle_ws_open_frame` accepts the ASGI `app` object directly rather than a URL — enables in-process WS transport without network
- `_agent_receive_loop_with_metadata` extended with `app: object` parameter; connect_and_serve passes the created app
- ASGIWebSocketTransport requires async context manager usage (`async with ASGIWebSocketTransport(...) as transport`)
- MockWSConnection in relay tests uses asyncio.Queue with None sentinel so agent_to_browser task blocks until explicitly stopped
- WS forwarding test uses asyncio.sleep(0.05) to allow relay browser_to_agent task to process message before disconnect

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_frame_type_has_seven_members assertion**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Original test asserted `len(FrameType) == 7`; after adding WS types this became 10
- **Fix:** Updated assertion to `len(FrameType) == 10` with explanatory comment
- **Files modified:** tests/tunnel/test_frames.py
- **Verification:** Test passes
- **Committed in:** ba8e4a5 (Task 1 feat commit)

**2. [Rule 1 - Bug] Fixed ASGIWebSocketTransport context manager usage**
- **Found during:** Task 1 (relay WS tests)
- **Issue:** `ASGIWebSocketTransport` requires `async with` to initialize `_task_group`; direct instantiation caused `AttributeError`
- **Fix:** Wrapped transport creation in `async with ASGIWebSocketTransport(...) as transport`
- **Files modified:** tests/relay/test_mount_proxy.py
- **Verification:** All relay WS tests pass
- **Committed in:** ba8e4a5 (Task 1 feat commit)

**3. [Rule 1 - Bug] Fixed MockWSConnection causing premature task completion**
- **Found during:** Task 1 (WS forwarding test)
- **Issue:** Original `MockWSConnection.read_stream_iter` used `_ws_response_event` that was set in `send_ws_open`, causing `agent_to_browser` task to complete immediately and cancel `browser_to_agent` before it could process messages
- **Fix:** Replaced with `asyncio.Queue` and None sentinel; agent_to_browser blocks until explicitly stopped
- **Files modified:** tests/relay/test_mount_proxy.py
- **Verification:** WS forwarding test passes with asyncio.sleep(0.05) yield
- **Committed in:** ba8e4a5 (Task 1 feat commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs — test infrastructure and API usage issues)
**Impact on plan:** All auto-fixes necessary for correct test behavior. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WebSocket tunneling complete: browser WS at /m/{code}/ws bridges to agent's local /ws
- All real-time features (clipboard, notifications, device discovery) now work through relay
- httpx-ws in production deps — agent package installable without dev extras
- 531 tests pass

---
*Phase: 11-remote-access-and-hardening*
*Completed: 2026-03-11*
