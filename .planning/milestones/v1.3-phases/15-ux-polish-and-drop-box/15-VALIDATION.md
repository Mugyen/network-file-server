---
phase: 15
slug: ux-polish-and-drop-box
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` (testpaths = ["server/tests", "tests"]) |
| **Quick run command** | `uv run pytest tests/relay/ server/tests/ -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/relay/ server/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-xx | 01 | 1 | LAND-01 | unit | `uv run pytest tests/relay/test_landing.py -x` | Exists (extend) | ⬜ pending |
| 15-01-xx | 01 | 1 | LAND-02 | unit | `uv run pytest tests/relay/test_landing.py::test_code_redirect_returns_302 -x` | Exists | ⬜ pending |
| 15-01-xx | 01 | 1 | LAND-03 | unit | `uv run pytest tests/relay/test_landing.py -x -k og` | ❌ W0 | ⬜ pending |
| 15-01-xx | 01 | 1 | LAND-04 | unit | `uv run pytest tests/relay/test_landing.py -x -k github` | ❌ W0 | ⬜ pending |
| 15-02-xx | 02 | 2 | CONN-01 | unit | `uv run pytest tests/relay/test_status.py -x` | ❌ W0 | ⬜ pending |
| 15-02-xx | 02 | 2 | CONN-02 | unit | `uv run pytest tests/relay/test_status.py -x` | ❌ W0 | ⬜ pending |
| 15-02-xx | 02 | 2 | CONN-03 | manual-only | N/A (visual check in browser) | N/A | ⬜ pending |
| 15-03-xx | 03 | 3 | DROP-01 | integration | `uv run pytest tests/relay/test_dropbox.py -x` | ❌ W0 | ⬜ pending |
| 15-03-xx | 03 | 3 | DROP-02 | unit | `uv run pytest tests/relay/test_config.py -x -k dropbox` | ❌ W0 | ⬜ pending |
| 15-03-xx | 03 | 3 | DROP-03 | unit | `uv run pytest tests/relay/test_dropbox.py -x -k reserved` | ❌ W0 | ⬜ pending |
| 15-03-xx | 03 | 3 | DROP-04 | unit | `uv run pytest tests/relay/test_landing.py -x -k dropbox` | ❌ W0 | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-01 | unit | `uv run pytest server/tests/test_upload.py -x -k ttl` | ❌ W0 | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-02 | unit | `uv run pytest server/tests/test_upload.py -x -k default_ttl` | ❌ W0 | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-03 | unit | `uv run pytest tests/relay/test_file_ttl.py -x` | ❌ W0 | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-04 | integration | `uv run pytest tests/relay/test_file_ttl.py -x -k toast` | ❌ W0 | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-05 | manual-only | N/A (visual check in browser) | N/A | ⬜ pending |
| 15-04-xx | 04 | 4 | FTTL-06 | integration | `uv run pytest tests/relay/test_file_ttl.py -x -k restart` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/relay/test_status.py` -- stubs for CONN-01, CONN-02 (status endpoint tests)
- [ ] `tests/relay/test_dropbox.py` -- stubs for DROP-01, DROP-03 (drop box init, reserved code)
- [ ] `tests/relay/test_file_ttl.py` -- stubs for FTTL-03, FTTL-04, FTTL-06 (file TTL sweep, toast, restart)
- [ ] Extend `tests/relay/test_landing.py` -- stubs for LAND-03, LAND-04, DROP-04 (OG tags, GitHub link, drop box link)
- [ ] Extend `tests/relay/test_config.py` -- stubs for DROP-02 (dropbox_code config field)
- [ ] Extend `server/tests/test_upload.py` -- stubs for FTTL-01, FTTL-02 (TTL param on upload)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Overlays replace partial UI with full-page message | CONN-03 | Visual layout / interaction check | Open SPA, disconnect agent, verify banner + greyed-out file list |
| Expiry badge in file listing | FTTL-05 | Visual rendering of countdown and color changes | Upload file with TTL, verify badge shows "Xh left", colors change at thresholds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
