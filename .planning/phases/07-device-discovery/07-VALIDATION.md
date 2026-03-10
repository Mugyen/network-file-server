---
phase: 07
slug: device-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest server/tests/test_websocket.py -x` |
| **Full suite command** | `uv run pytest server/tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest server/tests/test_websocket.py -x`
- **After every plan wave:** Run `uv run pytest server/tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | DISC-01, DISC-02 | unit + integration | `uv run pytest server/tests/test_websocket.py -x` | Extend existing | ⬜ pending |
| 07-01-02 | 01 | 1 | DISC-03, DISC-04 | integration | `uv run pytest server/tests/test_websocket.py -x` | Extend existing | ⬜ pending |
| 07-02-01 | 02 | 2 | DISC-01, DISC-02, DISC-04 | tsc | `cd client && npx tsc --noEmit` | New components | ⬜ pending |
| 07-02-02 | 02 | 2 | DISC-03 | tsc + full suite | `cd client && npx tsc --noEmit && uv run pytest server/tests/ -x` | App.tsx wiring | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Extend `server/tests/test_websocket.py` — new tests for device_list message, device_info in toasts, parse_device_type, your_device_id
- [ ] Update existing WebSocket tests for new `connect()` signature (IP, user_agent, connected_at parameters)

*Existing test infrastructure (pytest, conftest.py, httpx-ws async client) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Devices panel renders with correct layout | DISC-01 (frontend) | React component rendering | Open browser, click Devices button, verify panel shows |
| Device type icons display correctly | DISC-02 (frontend) | Icon rendering | Connect from phone + laptop, verify different icons |
| Real-time connect/disconnect animation | DISC-03 (frontend) | Visual transition | Open second browser, verify device appears/disappears |
| "You" badge on own device | DISC-04 (frontend) | Client-side identification | Open panel, verify "You" badge on own entry |
| Connection duration updates live | DISC-01 (frontend) | Timer rendering | Watch duration text change over time |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
