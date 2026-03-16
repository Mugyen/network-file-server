---
phase: 9
slug: relay-server
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| **Quick run command** | `uv run pytest tests/relay/ -x -q` |
| **Full suite command** | `uv run pytest server/tests/ tests/tunnel/ tests/relay/ -v` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/relay/ -x -q`
- **After every plan wave:** Run `uv run pytest server/tests/ tests/tunnel/ tests/relay/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 0 | RELY-01 | unit | `uv run pytest tests/relay/test_mount_registry.py -x` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 0 | RELY-03 | unit | `uv run pytest tests/relay/test_landing.py -x` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 0 | RELY-04 | unit | `uv run pytest tests/relay/test_mount_proxy.py -x -k "not_found or offline or expired"` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 0 | RELY-02 | unit | `uv run pytest tests/relay/test_mount_proxy.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `relay/__init__.py` — package root
- [ ] `relay/app/__init__.py`
- [ ] `relay/app/main.py` — `create_relay_app()` factory
- [ ] `relay/app/enums.py` — `MountStatus` enum
- [ ] `relay/app/exceptions.py` — `MountNotFoundError`, `MountOfflineError`, `MountExpiredError`
- [ ] `relay/app/services/mount_registry.py` — `MountRegistry` class
- [ ] `relay/app/routers/landing.py` — landing page + code redirect
- [ ] `relay/app/routers/mount_proxy.py` — HTTP proxy + error pages
- [ ] `relay/app/routers/agent_ws.py` — agent WebSocket endpoint
- [ ] `relay/templates/base.html` — shared Jinja2 layout
- [ ] `relay/templates/landing.html` — informational + code input
- [ ] `relay/templates/not_found.html` — includes code input for retry
- [ ] `relay/templates/offline.html` — offline message
- [ ] `relay/templates/expired.html` — expired message
- [ ] `tests/relay/conftest.py` — relay app fixture + MockTunnelConnection
- [ ] `tests/relay/test_mount_registry.py` — RELY-01 stubs
- [ ] `tests/relay/test_mount_proxy.py` — RELY-02, RELY-04 stubs
- [ ] `tests/relay/test_landing.py` — RELY-03 stubs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Landing page visual appearance | RELY-03 | CSS/layout rendering | Open relay in browser, verify informational text + code input visible |
| Error page visual appearance | RELY-04 | CSS/layout rendering | Navigate to invalid code, verify error page renders correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 8s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
