---
phase: 3
slug: search-preview-and-ui-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest server/tests/ -x -q` |
| **Full suite command** | `uv run pytest server/tests/ -v` |
| **Estimated runtime** | ~10 seconds |

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
| 03-01-01 | 01 | 1 | SRCH-01 | integration | `uv run pytest server/tests/test_search.py -x` | No -- Wave 0 | ⬜ pending |
| 03-01-02 | 01 | 1 | SRCH-02 | unit | `uv run pytest server/tests/test_file_service.py::test_search_files -x` | No -- Wave 0 | ⬜ pending |
| 03-01-03 | 01 | 1 | SRCH-03 | manual-only | Browser test: click column headers | N/A | ⬜ pending |
| 03-02-01 | 02 | 1 | MEDP-01 | integration | `uv run pytest server/tests/test_preview.py::test_image_preview -x` | No -- Wave 0 | ⬜ pending |
| 03-02-02 | 02 | 1 | MEDP-02 | integration | `uv run pytest server/tests/test_preview.py::test_range_request -x` | No -- Wave 0 | ⬜ pending |
| 03-02-03 | 02 | 1 | MEDP-03 | integration | `uv run pytest server/tests/test_preview.py::test_pdf_preview -x` | No -- Wave 0 | ⬜ pending |
| 03-02-04 | 02 | 1 | MEDP-04 | integration | `uv run pytest server/tests/test_preview.py::test_code_preview -x` | No -- Wave 0 | ⬜ pending |
| 03-02-05 | 02 | 1 | MEDP-05 | integration | `uv run pytest server/tests/test_preview.py::test_markdown_preview -x` | No -- Wave 0 | ⬜ pending |
| 03-03-01 | 03 | 2 | UIUX-01 | manual-only | Browser test: toggle dark mode, verify colors change | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `server/tests/test_search.py` — stubs for SRCH-01, SRCH-02 (search endpoint + recursive search service)
- [ ] `server/tests/test_preview.py` — stubs for MEDP-01 through MEDP-05 (preview endpoint, MIME types, Range requests)
- [ ] Extend `server/tests/conftest.py` — add sample image/video/code/markdown files to tmp_shared_folder fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Search bar filters file list instantly | SRCH-01 | Client-side UI interaction | Type in search bar, verify list filters in real-time |
| Sort by column headers | SRCH-03 | Client-side UI interaction | Click name/size/date/type column headers, verify sort order changes |
| Dark mode toggle | UIUX-01 | Visual verification | Toggle dark mode switch, verify all colors change; test system preference detection |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
