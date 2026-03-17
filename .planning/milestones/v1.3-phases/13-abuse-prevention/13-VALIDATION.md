---
phase: 13
slug: abuse-prevention
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/relay/ -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/relay/ -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | ABUSE-01 | integration | `uv run pytest tests/relay/test_rate_limit.py::test_mount_reg_rate_limit -x` | No -- Wave 0 | pending |
| 13-01-02 | 01 | 1 | ABUSE-02 | integration | `uv run pytest tests/relay/test_rate_limit.py::test_proxy_rate_limit -x` | No -- Wave 0 | pending |
| 13-01-03 | 01 | 1 | ABUSE-03 | unit + integration | `uv run pytest tests/relay/test_ttl.py -x` | No -- Wave 0 | pending |
| 13-01-04 | 01 | 1 | ABUSE-04 | unit + integration | `uv run pytest tests/relay/test_mount_cap.py -x` | No -- Wave 0 | pending |
| 13-01-05 | 01 | 1 | ABUSE-05 | integration | `uv run pytest tests/relay/test_rate_limit.py::test_429_retry_after -x` | No -- Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/relay/test_rate_limit.py` — stubs for ABUSE-01, ABUSE-02, ABUSE-05
- [ ] `tests/relay/test_ttl.py` — stubs for ABUSE-03 (TTL enforcement and background sweep)
- [ ] `tests/relay/test_mount_cap.py` — stubs for ABUSE-04 (per-IP mount cap)
- [ ] `tests/relay/test_config.py` — config module loading, validation, env var override
- [ ] `uv add slowapi` — new dependency

*Existing infrastructure covers pytest framework and test runner.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 429 styled error page renders correctly in browser | ABUSE-05 | Visual rendering check | Hit rate limit in browser, verify styled page with retry countdown |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
