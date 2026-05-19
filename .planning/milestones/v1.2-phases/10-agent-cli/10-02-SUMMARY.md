---
phase: 10-agent-cli
plan: "02"
subsystem: agent-cli
tags: [agent, websocket, asyncio, httpx, asgi, proxy, backoff, cli, argparse]

dependency_graph:
  requires:
    - phase: 10-01
      provides: WebSocketClientAdapter, display functions, compute_backoff, relay mount code generation
    - phase: 09-02
      provides: TunnelConnection, mount proxy router, relay agent WebSocket endpoint
  provides:
    - handle_open_frame — OPEN frame proxy to local ASGI app with DATA+CLOSE streaming
    - run_agent_loop — outer reconnect loop with exponential backoff and preferred-code reconnect
    - connect_and_serve — single WebSocket connection lifecycle with heartbeat and ASGI dispatch
    - run_mount — CLI entry point for mount subcommand
    - mount subcommand routing in server/app/cli.py
  affects: [agent/, server/app/cli.py]

tech-stack:
  added: []
  patterns:
    - "_agent_receive_loop: OPEN frames dispatched via asyncio.create_task; non-OPEN routed through conn._dispatch_frame"
    - "_parse_args detects subcommand via argv[0] check before calling separate parser — avoids argparse positional-vs-subparser conflict"
    - "finally block awaits pending tasks (not cancel) for graceful ASGI response completion on disconnect"
    - "asyncio_run alias in agent/cli.py and asyncio_sleep alias in agent/connection.py enable test patching without monkeypatching asyncio"

key-files:
  created:
    - agent/proxy.py
    - agent/connection.py
    - agent/cli.py
    - tests/agent/test_proxy.py
    - tests/agent/test_agent_connection.py
    - tests/agent/test_cli.py
  modified:
    - server/app/cli.py
    - docs/project-log.md

key-decisions:
  - "tests/agent/test_connection.py renamed to test_agent_connection.py to avoid basename collision with tests/tunnel/test_connection.py (no __init__.py convention means same basenames create pytest import errors)"
  - "_build_parser() returns LAN-mode-only parser (no subparsers); _parse_args() routes mount subcommand via separate _build_mount_parser() — keeps backward compat for tests calling _build_parser() directly"
  - "finally block awaits pending tasks (asyncio.gather) instead of cancelling — ensures in-flight ASGI responses complete cleanly when WebSocket disconnects"
  - "ConnectionError/EOFError/OSError caught in connect_and_serve for normal WebSocket disconnect (websockets raises these on clean close)"
  - "asyncio_run and asyncio_sleep module-level aliases enable test patching without global asyncio monkeypatching"

patterns-established:
  - "Coroutine leak prevention: tests that patch asyncio_run use side_effect=close_coro_and_return_none to avoid 'coroutine never awaited' warnings"

requirements-completed: [AGNT-01, AGNT-02, AGNT-04]

duration: 11min
completed: "2026-03-11"
tasks_completed: 2
files_changed: 8
---

# Phase 10 Plan 02: Agent Proxy, Connection Loop, and Mount CLI Summary

**`network-file-server mount ./files --server <url>` wires complete path: CLI → WebSocket → relay mount code → OPEN frame dispatch → local ASGI proxy → DATA+CLOSE streaming → exponential backoff reconnect**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-11T13:47:44Z
- **Completed:** 2026-03-11T13:58:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- `handle_open_frame` proxies OPEN frame metadata to local ASGI app via httpx ASGITransport, streams response as JSON metadata + body chunks, handles CANCEL via StreamNotFoundError, logs request line
- `run_agent_loop` / `connect_and_serve` implement full WebSocket lifecycle: receive mount code, start heartbeat, create local ASGI client, dispatch OPEN frames as concurrent tasks, reconnect with exponential backoff, track preferred code across reconnects
- `network-file-server mount ./files --server URL` and `network-file-server ./files` (LAN mode) both work; backward compatibility fully preserved

## Task Commits

1. **Task 1: Agent proxy — OPEN frame handler with ASGI dispatch** - `a7c9be6` (feat)
2. **Task 2: Agent connection loop, CLI subcommand, and graceful shutdown** - `f1c45e4` (feat)

## Files Created/Modified

- `agent/proxy.py` — handle_open_frame: OPEN frame → httpx ASGI dispatch → DATA+CLOSE streaming
- `agent/connection.py` — connect_and_serve, _agent_receive_loop, run_agent_loop with backoff
- `agent/cli.py` — run_mount entry point with folder validation and asyncio.run dispatch
- `server/app/cli.py` — Extended with _parse_args routing for mount subcommand; _build_parser unchanged for LAN backward compat
- `tests/agent/test_proxy.py` — 6 tests: metadata framing, 64K chunking, cancel, concurrent dispatch, query string
- `tests/agent/test_agent_connection.py` — 6 tests: mount_registered control, wrong type error, reconnect retry, preferred code, attempt reset, OPEN frame dispatch
- `tests/agent/test_cli.py` — 8 tests: mount parsing, --server required, --name optional, LAN backward compat, run_mount validation
- `docs/project-log.md` — Phase 10-02 entry

## Decisions Made

- `tests/agent/test_connection.py` renamed to `test_agent_connection.py` to avoid pytest basename collision with `tests/tunnel/test_connection.py` (no `__init__.py` convention means test files need unique basenames across all test directories)
- `_build_parser()` returns LAN-mode-only parser; `_parse_args()` checks `argv[0]` to route to mount parser — avoids argparse positional-vs-subparser namespace merge bug in Python 3.11
- `finally` block awaits pending tasks (not cancels) so in-flight ASGI responses complete when relay disconnects
- Module-level `asyncio_run = asyncio.run` and `asyncio_sleep = asyncio.sleep` aliases enable test patching without global monkeypatching

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Renamed test_connection.py to test_agent_connection.py**
- **Found during:** Task 2 full suite run
- **Issue:** Both `tests/agent/test_connection.py` and `tests/tunnel/test_connection.py` have the same basename; without `__init__.py` files, pytest treats them as the same module, causing `import file mismatch` error
- **Fix:** Renamed `tests/agent/test_connection.py` → `tests/agent/test_agent_connection.py`
- **Files modified:** tests/agent/test_agent_connection.py (renamed)
- **Verification:** `uv run pytest tests/ -x -q` — 155 tests pass
- **Committed in:** f1c45e4 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed argparse positional-vs-subparser namespace conflict**
- **Found during:** Task 2 CLI implementation
- **Issue:** Adding top-level `folder` (nargs='?') + subparsers in same argparse parser causes Python 3.11 to try the path argument against subparser choices, failing with "invalid choice" error
- **Fix:** Split into `_build_parser()` (LAN-only) and `_build_mount_parser()`, with `_parse_args()` routing based on argv[0] detection
- **Files modified:** server/app/cli.py
- **Verification:** Both `_parse_args(["mount", "/tmp", "--server", "URL"])` and `_parse_args(["/tmp"])` work correctly; 17 server CLI tests pass
- **Committed in:** f1c45e4 (Task 2 commit)

**3. [Rule 2 - Missing] Added task-awaiting in finally block instead of cancellation**
- **Found during:** Task 2 test for `_agent_receive_loop`
- **Issue:** Cancelling pending tasks in `finally` meant tasks created just before ConnectionError never ran; test showed only 1 of 2 dispatched ids populated
- **Fix:** Changed `finally` to `await asyncio.gather(*pending_tasks, return_exceptions=True)` without prior cancellation
- **Files modified:** agent/connection.py
- **Verification:** `test_agent_receive_loop_dispatches_open_frames` passes; both dispatched_ids populated
- **Committed in:** f1c45e4 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking rename, 1 bug fix, 1 missing behavior)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## Next Phase Readiness

- Full agent-side implementation complete: proxy, connection loop, reconnect, CLI
- Phase 10 is complete — `network-file-server mount` is functional end-to-end
- Next: Phase 11 (SPA base URL injection for relay-hosted UI) can proceed

## Self-Check: PASSED

- agent/proxy.py: FOUND
- agent/connection.py: FOUND
- agent/cli.py: FOUND
- tests/agent/test_proxy.py: FOUND
- tests/agent/test_agent_connection.py: FOUND
- tests/agent/test_cli.py: FOUND
- Commit a7c9be6: FOUND
- Commit f1c45e4: FOUND
- Full suite: 155 tests, 0 failures

---
*Phase: 10-agent-cli*
*Completed: 2026-03-11*
