---
phase: 16-wire-file-ttl-notifications
verified: 2026-04-03T13:10:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
---

# Phase 16: Wire File TTL Notifications — Verification Report

**Phase Goal:** Fix broadcast_fn wiring for TTL toast, add tunnel handlers for agent keep/delete responses (gap closure)
**Verified:** 2026-04-03T13:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When a drop box file is auto-deleted by the TTL sweep, all browsers connected to that mount see a toast notification | VERIFIED | `relay/app/main.py:75` passes `manager.broadcast_all` (not None) as `broadcast_fn`; `file_ttl_sweep.py:51-57` broadcasts full toast payload with `toast_type`, `device_name`, `timestamp`; `test_sweep_broadcasts_toast` asserts all fields |
| 2 | When an agent reconnects and responds to the expired-files prompt with delete or keep, the relay clears the expired TTL records | VERIFIED | `agent_ws.py:38-44` handles both `delete_expired_files` and `keep_expired_files` in `_handle_agent_control_for_mount` calling `delete_expired_for_mount`; `tunnel/connection.py:303-305` dispatches unknown message types to `_control_handler`; `agent_ws.py:231` registers the handler before `run_receive_loop`; `test_delete_expired_files_clears_records` and `test_keep_expired_files_clears_records` both pass |
| 3 | The relay default data directory is /tmp/relay-data and startup succeeds with this default | VERIFIED | `relay/config.yaml:8` sets `data_dir: /tmp/relay-data`; `test_load_config_data_dir_default` asserts `/tmp/relay-data` and passes |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `relay/app/services/dropbox.py` | Drop box ASGI app reference for WebSocket bridge | VERIFIED | `get_dropbox_app()` defined (line 65), raises `RuntimeError` if None; `set_dropbox_app()` defined (line 79); `_dropbox_app` stored in `init_dropbox()` (line 48) |
| `relay/app/routers/mount_proxy.py` | Drop box WebSocket bridge via ASGIWebSocketTransport | VERIFIED | `ASGIWebSocketTransport` imported (line 16); used in `proxy_websocket` (lines 293-318); bidirectional bridge with `asyncio.wait(FIRST_COMPLETED)` pattern |
| `relay/app/main.py` | broadcast_fn wired into run_file_ttl_sweep | VERIFIED | `manager.broadcast_all` passed explicitly at line 75; `from server.app.services.connection_manager import manager` imported at line 39 |
| `relay/app/services/file_ttl_sweep.py` | Full toast payload with toast_type, device_name, timestamp | VERIFIED | Lines 51-57 broadcast `{"type": "toast", "toast_type": "file_expired", "message": ..., "device_name": "System", "timestamp": datetime.now(timezone.utc).isoformat()}` |
| `tunnel/connection.py` | Generic control message callback in run_receive_loop | VERIFIED | `_control_handler` attribute initialized at line 57; `set_control_handler()` at line 265; `else` branch at lines 303-305 dispatches to handler |
| `relay/app/routers/agent_ws.py` | Handler for delete_expired_files and keep_expired_files messages | VERIFIED | `_handle_agent_control_for_mount()` module-level function (line 27); `conn.set_control_handler(_on_agent_control)` at line 231 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `relay/app/main.py` | `relay/app/services/file_ttl_sweep.py` | `manager.broadcast_all` passed as `broadcast_fn` | WIRED | Line 75: `run_file_ttl_sweep(..., 60, manager.broadcast_all)` — pattern `run_file_ttl_sweep.*broadcast_all` confirmed |
| `relay/app/routers/mount_proxy.py` | drop box server app's ConnectionManager | `ASGIWebSocketTransport` bridge keeps browser WS alive | WIRED | `get_dropbox_app()` called at line 282, `ASGIWebSocketTransport(app=app)` at line 293 — browser connections reach server app's WS handler |
| `relay/app/routers/agent_ws.py` | `tunnel/connection.py` | `set_control_handler` registers callback before `run_receive_loop` | WIRED | `conn.set_control_handler(_on_agent_control)` at line 231, `await conn.run_receive_loop()` at line 234 — registration confirmed before loop |
| `tunnel/connection.py` | `relay/app/services/file_ttl_db.py` | control handler calls `delete_expired_for_mount` on delete/keep | WIRED | `agent_ws.py:43` calls `await file_ttl_db.delete_expired_for_mount(code)` for both message types |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FTTL-04 | 16-01-PLAN.md | Connected browsers receive a WebSocket toast notification when a file is auto-deleted | SATISFIED | `broadcast_fn=manager.broadcast_all` wired; toast payload includes `toast_type="file_expired"`, `device_name`, `timestamp`; drop box WS bridge keeps browsers connected via `ASGIWebSocketTransport`; marked `[x]` in REQUIREMENTS.md |
| FTTL-06 | 16-01-PLAN.md | On mount restart, user is prompted whether to keep or delete files with expired TTLs | SATISFIED | `agent_ws.py` sends `expired_files` control on reclaim; `_handle_agent_control_for_mount` clears TTL records on `delete_expired_files`/`keep_expired_files`; `set_control_handler` wires the handler; marked `[x]` in REQUIREMENTS.md |

Both requirements declared in the PLAN frontmatter are accounted for and marked complete in REQUIREMENTS.md. No orphaned requirements found — REQUIREMENTS.md traceability table maps FTTL-04 and FTTL-06 exclusively to Phase 16.

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholder returns, or stub implementations found in the modified files.

One silent `except` block in `_handle_agent_control_for_mount` (`except RuntimeError: pass`) is intentional and carries an inline comment explaining why (`# FileTtlDb not initialized -- no-op`). This is a documented no-op for a known startup race, not a swallowed exception.

### Human Verification Required

None required for automated-verifiable aspects. One item for completeness:

**Drop box WS toast delivery end-to-end:** Verifying a real browser connected to the drop box mount actually displays a toast when a file's TTL expires requires a live relay instance with a running TTL sweep and a browser session. All code paths are verified; the integration test (`test_dropbox_ws_bridge_receives_initial_messages`) confirms the bridge forwards messages from the server app to the browser.

### Test Results

60 targeted tests pass across:

- `tests/relay/test_file_ttl.py` — sweep, toast payload assertions including `toast_type`, `device_name`, `timestamp`
- `tests/relay/test_dropbox_ws.py` — WS bridge connects and does not immediately close; receives initial server messages
- `tests/tunnel/test_connection.py` — control handler dispatch, ping/pong exclusion, silent drop for no handler
- `tests/relay/test_agent_expired_files.py` — `delete_expired_files` and `keep_expired_files` both clear TTL records
- `tests/relay/test_config.py` — `data_dir == "/tmp/relay-data"` assertion passes

### Gaps Summary

No gaps. All three observable truths are verified, all six artifacts are substantive and wired, all four key links are confirmed in the actual code, and both requirement IDs (FTTL-04, FTTL-06) are fully satisfied with test coverage.

---

_Verified: 2026-04-03T13:10:00Z_
_Verifier: Claude (gsd-verifier)_
