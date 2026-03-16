---
phase: 09-relay-server
plan: "02"
subsystem: relay
tags: [relay, websocket, proxy, streaming, tdd]
dependency_graph:
  requires:
    - relay package importable (09-01)
    - MountRegistry with lifecycle (09-01)
    - Jinja2 error templates (09-01)
    - TunnelConnection from tunnel/ (08-02)
  provides:
    - Agent WebSocket endpoint at /agent/ws
    - HTTP proxy router at /m/{code}/{path}
    - Fully functional relay server
  affects:
    - relay/app/main.py (two new routers mounted)
    - tests/relay/ (conftest expanded, test_mount_proxy added)
tech_stack:
  added: []
  patterns:
    - HOP_BY_HOP frozenset constant for O(1) header filtering
    - StreamingResponse wrapping async generator with disconnect detection
    - MockTunnelConnection with configurable first_chunk and body_chunks
    - registered_relay_client fixture returns (AsyncClient, registry) tuple
key_files:
  created:
    - relay/app/routers/agent_ws.py
    - relay/app/routers/mount_proxy.py
    - tests/relay/test_mount_proxy.py
  modified:
    - relay/app/main.py (include agent_ws and mount_proxy routers)
    - tests/relay/conftest.py (expanded MockTunnelConnection + new fixtures)
    - docs/project-log.md
decisions:
  - "HOP_BY_HOP is a frozenset of lowercase strings — header comparison uses .lower() for case-insensitive stripping"
  - "stream_generator checks is_disconnected() between chunks rather than before the first chunk — avoids race on fast responses"
  - "mock_connection and registered_relay_client fixtures avoid isinstance checks across conftest import paths (module identity issue with conftest)"
metrics:
  duration: "3m"
  completed_date: "2026-03-11"
  tasks_completed: 1
  files_created: 3
  tests_added: 9
---

# Phase 9 Plan 2: Agent WebSocket and Mount Proxy Summary

Agent WebSocket endpoint at /agent/ws registers TunnelConnection with heartbeat; HTTP proxy at /m/{code}/{path} streams responses with hop-by-hop stripping and Jinja2 error pages for all error states.

## What Was Built

### Task 1: Agent WebSocket endpoint and HTTP proxy router (TDD)

**RED:** Created `tests/relay/test_mount_proxy.py` with 9 failing tests covering
the full proxy lifecycle. Expanded `tests/relay/conftest.py` with a full
MockTunnelConnection interface and two new fixtures.

**GREEN:** Implemented the three production files:

- `relay/app/routers/agent_ws.py` — `@router.websocket("/agent/ws")` accepts the
  agent WebSocket, wraps it in `TunnelConnection`, calls `registry.register(code, conn)`,
  starts heartbeat with `HEARTBEAT_INTERVAL_S`/`HEARTBEAT_MISSED_LIMIT`, then awaits
  `conn.run_receive_loop()`. On disconnect (WebSocketDisconnect or any exit): calls
  `conn.close()` then `registry.deregister(code)` with MountNotFoundError swallowed
  in case heartbeat already cleaned up.

- `relay/app/routers/mount_proxy.py` — `@router.api_route("/m/{code}/{path:path}", methods=[...])`:
  - Catches MountNotFoundError (404 not_found.html), MountOfflineError (503 offline.html),
    MountExpiredError (410 expired.html) from `get_registry().get_connection(code)`
  - Strips `HOP_BY_HOP` headers and rewrites Host before building metadata dict
  - Opens stream, sends OPEN frame with metadata (body latin-1 encoded)
  - Reads first chunk via `read_stream(request_id, FIRST_BYTE_TIMEOUT_S)` — parses
    as response metadata JSON (status + headers)
  - Returns `StreamingResponse(stream_generator(), ...)` where the async generator
    yields from `read_stream_iter` and sends CANCEL on browser disconnect
  - Returns `Response("Gateway Timeout", status_code=504)` on FirstByteTimeoutError

- `relay/app/main.py` — Updated to include agent_ws and mount_proxy routers.

## Test Results

9 new tests in `tests/relay/test_mount_proxy.py`:
- `test_proxy_get` — 200 response with body from mock stream
- `test_proxy_send_open_metadata` — correct method and path in OPEN metadata
- `test_proxy_post_body` — POST body forwarded in metadata
- `test_proxy_not_found` — 404 with HTML containing "not found" / "mount"
- `test_not_found_has_code_input` — not_found template has code input element
- `test_proxy_offline` — 503 with "offline" in HTML
- `test_proxy_expired_page` — 410 with "expired" in HTML
- `test_proxy_strips_hop_by_hop_headers` — Connection/Transfer-Encoding absent from metadata
- `test_proxy_first_byte_timeout` — 504 on FirstByteTimeoutError

Full suite: 424 tests passing (relay + tunnel + server).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed isinstance checks using cross-conftest imports**
- **Found during:** Task 1 GREEN phase
- **Issue:** `from tests.relay.conftest import MockTunnelConnection` in a test file
  creates a different class object than the one pytest instantiates via the conftest
  module (two different module paths). isinstance() returned False.
- **Fix:** Removed isinstance assertions — tests check conn attributes directly
  (sent_opens, cancelled_streams, etc.) without type checking.
- **Files modified:** tests/relay/test_mount_proxy.py
- **Commit:** 07fa867

## Self-Check: PASSED

Key files verified:
- relay/app/routers/agent_ws.py: FOUND
- relay/app/routers/mount_proxy.py: FOUND
- tests/relay/test_mount_proxy.py: FOUND

Commits verified:
- 07fa867: feat(09-02): agent WebSocket endpoint and mount proxy router
