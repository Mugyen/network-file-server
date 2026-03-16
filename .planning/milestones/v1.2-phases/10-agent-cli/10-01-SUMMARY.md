---
phase: 10-agent-cli
plan: "01"
subsystem: agent-cli
tags: [relay, agent, websocket, backoff, display, tdd]
dependency_graph:
  requires: [09-02]
  provides: [relay-mount-code-generation, agent-ws-adapter, agent-display, agent-backoff]
  affects: [relay/app/routers/agent_ws.py, agent/]
tech_stack:
  added: [websockets>=13.0 (production dep), httpx moved to production deps]
  patterns: [ASGIWebSocketTransport for in-process WS testing, structural Protocol compliance]
key_files:
  created:
    - agent/__init__.py
    - agent/ws_adapter.py
    - agent/backoff.py
    - agent/display.py
    - tests/agent/conftest.py
    - tests/agent/test_ws_adapter.py
    - tests/agent/test_display.py
    - tests/agent/test_backoff.py
    - tests/relay/test_agent_ws.py
  modified:
    - relay/app/routers/agent_ws.py
    - pyproject.toml
    - uv.lock
    - docs/project-log.md
decisions:
  - "tests/agent/ has no __init__.py — prevents sys.path shadowing of agent/ package (same convention as tests/tunnel/ and tests/relay/)"
  - "httpx_ws.transport.ASGIWebSocketTransport used for in-process WebSocket testing (not httpx.ASGITransport which only handles HTTP)"
  - "Relay generates mount code before sending control message — agent connects, relay assigns, agent learns its code via mount_registered"
  - "compute_backoff uses uniform jitter in [-jitter_factor, +jitter_factor] * exp_delay range (not one-sided)"
  - "websockets>=13.0 added as production dependency alongside httpx"
metrics:
  duration: 11m
  completed_date: "2026-03-11"
  tasks_completed: 2
  files_changed: 12
---

# Phase 10 Plan 01: Agent Package Foundation Summary

Relay generates mount codes server-side with preferred-code reconnect support, and new `agent/` package provides WebSocketClientAdapter, terminal display, and exponential backoff primitives.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Relay protocol: generate mount code, send mount_registered | 6ee8b5b | relay/app/routers/agent_ws.py, tests/relay/test_agent_ws.py |
| 2 | Agent package: ws_adapter, display, backoff, httpx prod dep | 3cc4ab2 | agent/*.py, tests/agent/*, pyproject.toml |

## What Was Built

### Relay Protocol Change (Task 1)

Modified `relay/app/routers/agent_ws.py`:
- Changed `code: str = Query(...)` to `code: str | None = Query(None)` — optional preferred code for reconnect
- If preferred code provided and not occupied → reuse it; otherwise generate with `generate_mount_code()`
- After `register(assigned_code, conn)`, sends `{"type": "mount_registered", "code": assigned_code}` control message
- Deregisters `assigned_code` (not the old parameter) in the finally block

### Agent Package (Task 2)

**`agent/ws_adapter.py`**: `WebSocketClientAdapter` wrapping `websockets.asyncio.client.ClientConnection`. Satisfies `WebSocketProtocol` structural interface via runtime-checkable Protocol. Constructor validates isinstance, raises TypeError for wrong types. `receive_bytes`/`receive_text` raise TypeError if wrong frame type received.

**`agent/display.py`**: Terminal display functions — `print_mounted` (QR + mount URL + code + folder + relay URL), `print_request_line` (one-liner per request), `print_reconnect_status`, `print_connected_status`. Reuses `generate_ascii_qr` from `server.app.services.qr_service`.

**`agent/backoff.py`**: `compute_backoff(attempt, base, cap, jitter_factor)` — strict input validation (ValueError for all bad inputs), uniform jitter, always returns >= 0.

**`pyproject.toml`**: Moved `httpx>=0.28.0` to `[project.dependencies]`; added `websockets>=13.0` as production dep; removed httpx from dev group; added `agent` to hatch packages list.

## Test Results

- 5 new relay tests (test_agent_ws.py) — all pass
- 32 new agent tests (test_ws_adapter, test_display, test_backoff) — all pass
- Full suite: 132 tests, 0 failures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] httpx_ws.ASGIWebSocketTransport needed for in-process WebSocket testing**
- **Found during:** Task 1 RED/GREEN
- **Issue:** `httpx.ASGITransport` handles HTTP only; WebSocket upgrade returns 404 via ASGI transport
- **Fix:** Used `httpx_ws.transport.ASGIWebSocketTransport` instead — designed specifically for testing ASGI WebSocket endpoints in-process
- **Files modified:** tests/relay/test_agent_ws.py
- **Commit:** 6ee8b5b

**2. [Rule 2 - Missing] websockets added as explicit production dependency**
- **Found during:** Task 2 implementation
- **Issue:** `agent/ws_adapter.py` imports `websockets.asyncio.client.ClientConnection`; websockets was not listed as a project dependency
- **Fix:** Added `websockets>=13.0` to `[project.dependencies]` in pyproject.toml
- **Files modified:** pyproject.toml, uv.lock
- **Commit:** 3cc4ab2

## Self-Check: PASSED

All files created: agent/__init__.py, agent/ws_adapter.py, agent/display.py, agent/backoff.py, all test files.
All commits verified: 4100faa, 6ee8b5b, 5c81cda, 3cc4ab2.
