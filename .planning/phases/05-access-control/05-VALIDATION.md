---
phase: 5
slug: access-control
status: draft
nyquist_compliant: true
wave_0_complete: true
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

## Nyquist Compliance Note

Wave 0 is satisfied by inline TDD tasks in Plans 01 and 02. Each TDD task writes tests (RED) before implementation (GREEN), so test files are created as part of the task itself. No separate Wave 0 stub plan is needed because:
- Plan 01 Task 1 (tdd=true): creates `test_cli.py`, `test_config.py` tests inline
- Plan 01 Task 2 (tdd=true): creates `test_auth_service.py` tests inline
- Plan 02 Task 1 (tdd=true): creates `test_auth.py` tests inline
- Plan 02 Task 2 (tdd=true): creates `test_read_only.py`, `test_receive_mode.py` tests inline
- Plan 01 Task 1 also creates conftest.py fixtures used by Plan 02 tests

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-T1 | 01 | 1 | AUTH-01, AUTH-03, AUTH-08 | unit | `uv run pytest server/tests/test_cli.py server/tests/test_config.py -x -q` | TDD inline | pending |
| 05-01-T2 | 01 | 1 | AUTH-03 | unit | `uv run pytest server/tests/test_auth_service.py -x -q` | TDD inline | pending |
| 05-02-T1 | 02 | 2 | AUTH-02 | integration | `uv run pytest server/tests/test_auth.py -x -q` | TDD inline | pending |
| 05-02-T2 | 02 | 2 | AUTH-04, AUTH-06 | integration | `uv run pytest server/tests/test_read_only.py server/tests/test_receive_mode.py -x -q` | TDD inline | pending |
| 05-03-T1 | 03 | 3 | AUTH-02, AUTH-05 | compile | `cd client && npx tsc --noEmit` | N/A (frontend) | pending |
| 05-03-T2 | 03 | 3 | AUTH-07 | compile | `cd client && npx tsc --noEmit` | N/A (frontend) | pending |
| 05-03-T3 | 03 | 3 | AUTH-05 | compile | `cd client && npx tsc --noEmit` | N/A (frontend) | pending |
| 05-03-T4 | 03 | 3 | ALL | manual | Visual verification of all 6 scenarios | N/A (checkpoint) | pending |

*Status: pending -- green -- red -- flaky*

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered via TDD inline test creation (no separate stub plan needed)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
