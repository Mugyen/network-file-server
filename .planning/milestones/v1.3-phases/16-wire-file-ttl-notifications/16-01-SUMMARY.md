---
phase: 16-wire-file-ttl-notifications
plan: 01
subsystem: api
tags: [websocket, asgi, file-ttl, toast-notifications, tunnel]

# Dependency graph
requires:
  - phase: 15-ux-polish-and-drop-box
    provides: "Drop box ASGI app, file TTL sweep, mount proxy WS endpoint"
  - phase: 14-persistent-mount-registry
    provides: "SqliteMountRegistry with mount reclaim, FileTtlDb"
provides:
  - "broadcast_fn wired into file TTL sweep (not None)"
  - "Drop box WS bridge via ASGIWebSocketTransport (browser connections stay alive)"
  - "Full toast payload with toast_type, device_name, timestamp"
  - "TunnelConnection.set_control_handler for app-specific control messages"
  - "Agent expired-files response handler (delete/keep clears TTL records)"
  - "FILE_EXPIRED enum value in server and client ToastType"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [ASGIWebSocketTransport bridge for drop box WS, generic control handler callback in TunnelConnection]

key-files:
  created:
    - tests/relay/test_dropbox_ws.py
  modified:
    - relay/app/services/dropbox.py
    - relay/app/services/file_ttl_sweep.py
    - relay/app/main.py
    - relay/app/routers/mount_proxy.py
    - relay/app/routers/agent_ws.py
    - tunnel/connection.py
    - server/app/models/enums.py
    - client/src/types/websocket.ts
    - tests/relay/test_file_ttl.py
    - tests/tunnel/test_connection.py
    - tests/relay/test_agent_expired_files.py
    - tests/relay/test_config.py

key-decisions:
  - "Reused ASGIWebSocketTransport bridge pattern from agent/proxy.py for drop box WS"
  - "Exposed _handle_agent_control_for_mount as module-level function for testability"
  - "Generic set_control_handler callback rather than hardcoding message types in tunnel"

patterns-established:
  - "TunnelConnection control handler: register app-specific message handlers via set_control_handler() instead of modifying the tunnel protocol"
  - "Drop box WS bridge: use same ASGIWebSocketTransport bidirectional pattern as agent/proxy.py"

requirements-completed: [FTTL-04, FTTL-06]

# Metrics
duration: 9min
completed: 2026-04-03
---

# Phase 16 Plan 01: Wire File TTL Notifications Summary

**Wired broadcast_fn into file TTL sweep, bridged drop box WS via ASGIWebSocketTransport, added tunnel control handler for agent expired-files responses**

## Performance

- **Duration:** 9 min
- **Started:** 2026-04-03T12:41:58Z
- **Completed:** 2026-04-03T12:51:54Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Wired manager.broadcast_all as broadcast_fn in run_file_ttl_sweep (was None) so file TTL auto-deletion sends WebSocket toast notifications to browsers
- Replaced drop box WS accept-and-close with ASGIWebSocketTransport bridge so browsers can receive real-time toast notifications
- Added TunnelConnection.set_control_handler() and agent_ws.py handler so relay processes agent keep/delete responses for expired files on mount reclaim
- Fixed toast payload to include toast_type, device_name, timestamp fields matching WSToastPayload interface
- Added FILE_EXPIRED to both server and client ToastType enums
- Fixed stale test_load_config_data_dir_default assertion (/data/ -> /tmp/relay-data)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire broadcast_fn, store drop box app, fix toast payload, bridge drop box WS (FTTL-04)** - `64a2fc1` (test), `27aa460` (feat)
2. **Task 2: Add tunnel control handler for agent expired-files responses (FTTL-06) and fix config test** - `fad43c3` (test), `43e2bcf` (feat)

_TDD tasks have separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `relay/app/services/dropbox.py` - Added get_dropbox_app/set_dropbox_app for ASGI app singleton
- `relay/app/services/file_ttl_sweep.py` - Fixed toast payload with toast_type, device_name, timestamp
- `relay/app/main.py` - Wired manager.broadcast_all as broadcast_fn (was None)
- `relay/app/routers/mount_proxy.py` - Replaced WS accept-and-close with ASGIWebSocketTransport bridge
- `relay/app/routers/agent_ws.py` - Added _handle_agent_control_for_mount and set_control_handler registration
- `tunnel/connection.py` - Added set_control_handler and else branch in run_receive_loop
- `server/app/models/enums.py` - Added FILE_EXPIRED to ToastType enum
- `client/src/types/websocket.ts` - Added FILE_EXPIRED to client ToastType const
- `tests/relay/test_dropbox_ws.py` - New: WS bridge lifecycle and message forwarding tests
- `tests/relay/test_file_ttl.py` - Updated toast payload assertions
- `tests/tunnel/test_connection.py` - Added control handler dispatch, ping/pong exclusion, silent drop tests
- `tests/relay/test_agent_expired_files.py` - Added delete_expired_files and keep_expired_files handler tests
- `tests/relay/test_config.py` - Fixed stale data_dir assertion
- `docs/project-log.md` - Phase 16 entry

## Decisions Made
- Reused the ASGIWebSocketTransport bidirectional bridge pattern from agent/proxy.py for the drop box WS connection, keeping consistent architecture across relay and agent
- Made TunnelConnection.set_control_handler() generic rather than hardcoding specific message types, so the tunnel protocol remains clean and extensible
- Exposed _handle_agent_control_for_mount as a module-level function in agent_ws.py so tests can call it directly without full WS flow simulation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 32 v1.3 requirements satisfied (FTTL-04 and FTTL-06 were the last two)
- All E2E flows working: drop box file TTL toast flow and agent expired files response flow
- Full test suite green (702 tests)

## Self-Check: PASSED

All 14 files verified present. All 5 commits verified in git log. 702 tests passing.

---
*Phase: 16-wire-file-ttl-notifications*
*Completed: 2026-04-03*
