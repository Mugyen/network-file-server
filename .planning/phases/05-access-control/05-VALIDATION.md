---
phase: 5
slug: access-control
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest server/tests/ -x -q` |
| **Full suite command** | `uv run pytest server/tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest server/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest server/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | AUTH-01 | unit | `uv run pytest server/tests/test_cli.py -x -q` | ✅ extend | ⬜ pending |
| 05-01-02 | 01 | 1 | AUTH-01 | unit | `uv run pytest server/tests/test_config.py -x -q` | ✅ extend | ⬜ pending |
| 05-01-03 | 01 | 1 | AUTH-08 | unit | `uv run pytest server/tests/test_cli.py -x -q` | ✅ extend | ⬜ pending |
| 05-02-01 | 02 | 1 | AUTH-02 | integration | `uv run pytest server/tests/test_auth.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | AUTH-03 | integration | `uv run pytest server/tests/test_auth.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 1 | AUTH-03 | integration | `uv run pytest server/tests/test_auth.py -x -q` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 1 | AUTH-04 | integration | `uv run pytest server/tests/test_read_only.py -x -q` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 1 | AUTH-05 | integration | `uv run pytest server/tests/test_routes_info.py -x -q` | ✅ extend | ⬜ pending |
| 05-04-01 | 04 | 1 | AUTH-06 | integration | `uv run pytest server/tests/test_receive_mode.py -x -q` | ❌ W0 | ⬜ pending |
| 05-04-02 | 04 | 1 | AUTH-07 | integration | `uv run pytest server/tests/test_receive_mode.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `server/tests/test_auth.py` — stubs for AUTH-02, AUTH-03 (login endpoint, session cookie, middleware)
- [ ] `server/tests/test_read_only.py` — stubs for AUTH-04 (all write endpoints blocked)
- [ ] `server/tests/test_receive_mode.py` — stubs for AUTH-06, AUTH-07 (receive mode restrictions, upload works)
- [ ] `server/tests/conftest.py` — fixtures for app variants (with password, read-only, receive)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Login form renders correctly | AUTH-02 | Visual UI verification | Start with `--password secret`, open browser, verify login form layout |
| Drop box UI shows drag zone | AUTH-07 | Visual UI verification | Start with `--receive`, open browser, verify centered drop zone |
| Mode badges display in header | AUTH-05 | Visual UI verification | Start with `--read-only`, verify amber "Read Only" badge |
| Terminal banner shows modes | AUTH-01/04/06 | CLI output verification | Start with flags, verify terminal output includes active modes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
