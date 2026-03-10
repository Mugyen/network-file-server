---
phase: 06
slug: expiring-share-links
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest server/tests/test_share.py server/tests/test_share_service.py -x` |
| **Full suite command** | `uv run pytest server/tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest server/tests/test_share.py server/tests/test_share_service.py -x`
- **After every plan wave:** Run `uv run pytest server/tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | SHARE-01, SHARE-02 | unit | `uv run pytest server/tests/test_share_service.py -x` | No -- Wave 0 | ⬜ pending |
| 06-01-02 | 01 | 1 | SHARE-05 | integration | `uv run pytest server/tests/test_share.py::test_share_bypasses_auth -x` | No -- Wave 0 | ⬜ pending |
| 06-02-01 | 02 | 2 | SHARE-03, SHARE-04 | integration | `uv run pytest server/tests/test_share.py::test_download_page_renders -x` | No -- Wave 0 | ⬜ pending |
| 06-02-02 | 02 | 2 | SHARE-06, SHARE-07 | unit + integration | `uv run pytest server/tests/test_share.py::test_list_active_links -x` | No -- Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `server/tests/test_share_service.py` — unit tests for ShareLinkService (create, validate, revoke, expiry, cleanup)
- [ ] `server/tests/test_share.py` — integration tests for share router endpoints (create link, download page, expired page, auth bypass, list, revoke)
- [ ] Share service fixture in `server/tests/conftest.py` — `configured_app_with_shares` fixture

*Existing test infrastructure (pytest, conftest.py, httpx async client) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Share button appears in file row UI | SHARE-01 (frontend) | React component rendering | Open browser, hover file row, verify Share button visible |
| TTL dropdown shows 4 options | SHARE-02 (frontend) | UI interaction | Click Share, verify dropdown shows 15min/1hr/6hr/24hr |
| Copy-to-clipboard works | SHARE-01 (frontend) | Browser clipboard API | Create share link, click Copy, paste to verify URL |
| Download page renders correctly | SHARE-03 (frontend) | Server-rendered template styling | Open share link in incognito, verify layout |
| Expired page renders correctly | SHARE-04 (frontend) | Server-rendered template styling | Wait for link to expire, verify "expired" message |
| Active links panel in UI | SHARE-06 (frontend) | React component rendering | Open active links panel, verify list displays |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
