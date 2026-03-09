---
phase: 4
slug: real-time-features
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest server/tests/ -x --timeout=10` |
| **Full suite command** | `uv run pytest server/tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest server/tests/ -x --timeout=10`
- **After every plan wave:** Run `uv run pytest server/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | RTME-01 | integration | `uv run pytest server/tests/test_websocket.py::TestWebSocketConnect -x` | No -- Wave 0 | ⬜ pending |
| 04-01-02 | 01 | 1 | RTME-01 | integration | `uv run pytest server/tests/test_websocket.py::TestDeviceTracking -x` | No -- Wave 0 | ⬜ pending |
| 04-01-03 | 01 | 1 | RTME-02 | integration | `uv run pytest server/tests/test_websocket.py::TestToastBroadcast -x` | No -- Wave 0 | ⬜ pending |
| 04-01-04 | 01 | 1 | N/A | unit | `uv run pytest server/tests/test_persistence.py -x` | No -- Wave 0 | ⬜ pending |
| 04-02-01 | 02 | 2 | RTME-03 | unit | `uv run pytest server/tests/test_clipboard_service.py -x` | No -- Wave 0 | ⬜ pending |
| 04-02-02 | 02 | 2 | RTME-03 | integration | `uv run pytest server/tests/test_websocket.py::TestClipboardSync -x` | No -- Wave 0 | ⬜ pending |
| 04-02-03 | 02 | 2 | RTME-04 | unit | `uv run pytest server/tests/test_file_request_service.py -x` | No -- Wave 0 | ⬜ pending |
| 04-02-04 | 02 | 2 | RTME-04 | integration | `uv run pytest server/tests/test_websocket.py::TestFileRequestBroadcast -x` | No -- Wave 0 | ⬜ pending |
| 04-02-05 | 02 | 2 | RTME-05 | unit+integration | `uv run pytest server/tests/test_file_request_service.py::TestFulfillment -x` | No -- Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `server/tests/test_websocket.py` — WebSocket connect, broadcast, device tracking, message routing (uses Starlette TestClient `websocket_connect`)
- [ ] `server/tests/test_clipboard_service.py` — Clipboard snippet CRUD, persistence
- [ ] `server/tests/test_file_request_service.py` — File request CRUD, fulfillment, persistence
- [ ] `server/tests/test_persistence.py` — Atomic JSON read/write utility

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Toast appears on remote device on file upload | RTME-02 | Multi-device visual verification | Open app on 2 devices, upload file on device A, verify toast on device B |
| Clipboard text syncs in real-time across devices | RTME-03 | Multi-device real-time visual | Open scratchpad on 2 devices, type on device A, verify text appears on device B |
| File request banner visible on other devices | RTME-04 | Multi-device visual verification | Create request on device A, verify banner on device B |
| Drag file onto request banner to fulfill | RTME-05 | Browser interaction | Create request on device A, drag file onto banner on device B |
| Reconnection after network drop | RTME-01 | Network disruption scenario | Disconnect WiFi briefly, reconnect, verify WebSocket re-establishes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
