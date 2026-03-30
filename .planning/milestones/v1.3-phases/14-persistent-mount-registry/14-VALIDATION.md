---
phase: 14
slug: persistent-mount-registry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run python -m pytest tests/relay/ -x -q` |
| **Full suite command** | `uv run python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/relay/ -x -q`
- **After every plan wave:** Run `uv run python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | PERS-01 | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py -x` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | PERS-02 | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_startup_marks_online_as_offline -x` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 1 | PERS-03 | unit+integration | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_reclaim_offline_mount -x` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 1 | PERS-04 | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_delete_expired_retention -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/relay/test_sqlite_registry.py` — stubs for PERS-01 through PERS-04 (schema init, CRUD, startup cleanup, reclaim, retention deletion)
- [ ] Update `tests/relay/conftest.py` — fixtures need async registry creation with `:memory:` DB
- [ ] Update all existing tests that use `MountRegistry()` directly — switch to async-compatible setup
- [ ] `aiosqlite` dependency: `uv add aiosqlite` — not currently installed

*Wave 0 tasks create test infrastructure before feature code.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Relay restart preserves mounts | PERS-01 | Requires process restart | Start relay, register mount via agent, kill relay, restart, verify mount shows as offline |
| Agent reconnect reclaims code | PERS-03 | Requires agent WebSocket lifecycle | Start agent, register mount, disconnect agent, reconnect with same code, verify reclaimed response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
