---
phase: 12
slug: cloud-run-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/relay/ -x` |
| **Full suite command** | `uv run pytest tests/relay/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/relay/ -x`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | DEPLOY-01 | smoke | Manual: `docker build . && docker run -e PORT=8080 -p 8080:8080` then `curl localhost:8080/health` | N/A (manual) | ⬜ pending |
| 12-01-02 | 01 | 1 | DEPLOY-02 | unit | `uv run pytest tests/relay/test_health.py -x` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | DEPLOY-03 | unit | `uv run pytest tests/relay/test_logging.py -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 1 | DEPLOY-04 | unit | `uv run pytest tests/relay/test_secure_cookies.py -x` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 1 | DEPLOY-05 | unit | `uv run pytest tests/relay/test_cors.py -x` | ❌ W0 | ⬜ pending |
| 12-02-03 | 02 | 1 | DEPLOY-06 | unit | `uv run pytest tests/relay/test_proxy_headers.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/relay/test_health.py` — stubs for DEPLOY-02
- [ ] `tests/relay/test_logging.py` — stubs for DEPLOY-03
- [ ] `tests/relay/test_secure_cookies.py` — stubs for DEPLOY-04
- [ ] `tests/relay/test_cors.py` — stubs for DEPLOY-05
- [ ] `tests/relay/test_proxy_headers.py` — stubs for DEPLOY-06

*Existing infrastructure covers test framework (pytest already configured).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Container starts on $PORT and serves requests | DEPLOY-01 | Docker build and run requires Docker daemon | `docker build -t relay . && docker run -e PORT=8080 -p 8080:8080 relay` then `curl localhost:8080/health` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
