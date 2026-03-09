---
phase: 2
slug: file-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest server/tests/ -x -q` |
| **Full suite command** | `uv run pytest server/tests/ -v` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest server/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest server/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | FILE-01, FILE-02 | unit/integration | `uv run pytest server/tests/test_routes_files.py -x` | ✅ (extend) | ⬜ pending |
| 02-01-02 | 01 | 0 | FILE-03 | integration | `uv run pytest server/tests/test_upload.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | FILE-04, FILE-05 | integration | `uv run pytest server/tests/test_download.py -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | FILE-06, FILE-07, FILE-08, FILE-09 | integration | `uv run pytest server/tests/test_file_operations.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 0 | UIUX-03 | unit | `uv run pytest server/tests/test_file_service.py -x` | ✅ (extend) | ⬜ pending |
| 02-02-02 | 02 | 0 | UIUX-02 | manual | N/A | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `server/tests/test_upload.py` — covers FILE-03 (upload endpoint, multi-file, path traversal on upload)
- [ ] `server/tests/test_download.py` — covers FILE-04, FILE-05 (single download, ZIP download, path traversal on download)
- [ ] `server/tests/test_file_operations.py` — covers FILE-06, FILE-07, FILE-08, FILE-09 (delete, rename, mkdir, batch delete, path traversal on each)
- [ ] Extend `server/tests/test_routes_files.py` — covers FILE-01, FILE-02 (browse + navigate subdirs)
- [ ] Extend `server/tests/test_file_service.py` — covers UIUX-03 icon mapping if backend involved

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Responsive mobile layout | UIUX-02 | Visual layout verification | 1. Open browser dev tools 2. Toggle mobile viewport 3. Verify file list, toolbar, breadcrumbs adapt |
| Drag-and-drop overlay | FILE-03 | Browser drag event interaction | 1. Drag files over browser window 2. Verify overlay appears 3. Drop files 4. Verify upload starts |
| Upload floating panel | FILE-03 | Visual component verification | 1. Upload multiple files 2. Verify floating panel with individual progress bars |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
