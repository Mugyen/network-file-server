---
phase: 16
slug: wire-file-ttl-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run python -m pytest tests/relay/test_file_ttl.py tests/relay/test_agent_expired_files.py tests/relay/test_config.py tests/tunnel/test_connection.py -x -q` |
| **Full suite command** | `uv run python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/relay/test_file_ttl.py tests/relay/test_agent_expired_files.py tests/relay/test_config.py tests/tunnel/test_connection.py -x -q`
- **After every plan wave:** Run `uv run python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | FTTL-04 | unit | `uv run python -m pytest tests/relay/test_file_ttl.py::test_sweep_broadcasts_toast -x` | ✅ | ⬜ pending |
| 16-01-02 | 01 | 1 | FTTL-04 | unit | `uv run python -m pytest tests/relay/test_dropbox_ws.py -x` | ❌ W0 | ⬜ pending |
| 16-01-03 | 01 | 1 | FTTL-06 | unit | `uv run python -m pytest tests/tunnel/test_connection.py::test_control_handler_dispatch -x` | ❌ W0 | ⬜ pending |
| 16-01-04 | 01 | 1 | FTTL-06 | integration | `uv run python -m pytest tests/relay/test_agent_expired_files.py -x` | ✅ partial | ⬜ pending |
| 16-01-05 | 01 | 1 | tech-debt | unit | `uv run python -m pytest tests/relay/test_config.py::test_load_config_data_dir_default -x` | ✅ failing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/relay/test_dropbox_ws.py` — stubs for FTTL-04 WS bridge behavior
- [ ] `tests/tunnel/test_connection.py::test_control_handler_*` — stubs for FTTL-06 generic control handler dispatch
- [ ] `tests/relay/test_agent_expired_files.py` — extend with agent->relay direction test (delete/keep response handling)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
