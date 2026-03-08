---
phase: 1
slug: foundation-and-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Framework (frontend)** | Vitest 4.0.18 + @testing-library/react 16.3.2 |
| **Config file (backend)** | none — Wave 0 installs |
| **Config file (frontend)** | none — Wave 0 installs |
| **Quick run command (backend)** | `uv run pytest tests/ -x` |
| **Quick run command (frontend)** | `cd client && npx vitest run --reporter=verbose` |
| **Full suite command** | `uv run pytest tests/ && cd client && npx vitest run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x`
- **After every plan wave:** Run `uv run pytest tests/ && cd client && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | FOUND-03 | unit | `uv run pytest tests/test_file_service.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | FOUND-01 | integration | `uv run pytest tests/test_routes_spa.py -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 0 | FOUND-02 | unit | `uv run pytest tests/test_config.py -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 0 | FOUND-04 | integration | `uv run pytest tests/test_cors.py -x` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 0 | DISC-01 | unit | `uv run pytest tests/test_qr_service.py -x` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 0 | DISC-02 | integration | `uv run pytest tests/test_routes_info.py -x` | ❌ W0 | ⬜ pending |
| 01-01-07 | 01 | 0 | DISC-03 | unit | `uv run pytest tests/test_network.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures: test client via httpx `ASGITransport`, temp shared folder with sample files
- [ ] `tests/test_file_service.py` — stubs for FOUND-03 (path traversal)
- [ ] `tests/test_routes_files.py` — covers file listing API
- [ ] `tests/test_routes_info.py` — covers DISC-02 (QR SVG endpoint)
- [ ] `tests/test_routes_spa.py` — covers FOUND-01 (SPA serving)
- [ ] `tests/test_config.py` — covers FOUND-02 (CLI args)
- [ ] `tests/test_cors.py` — covers FOUND-04
- [ ] `tests/test_qr_service.py` — covers DISC-01 (ASCII QR)
- [ ] `tests/test_network.py` — covers DISC-03 (IP detection)
- [ ] `client/src/__tests__/` directory — frontend component tests
- [ ] pytest + pytest-asyncio + httpx as dev dependencies: `uv add --dev pytest pytest-asyncio httpx`
- [ ] Vitest + testing-library as dev dependencies: `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
- [ ] `pyproject.toml` pytest config section (testpaths, asyncio_mode)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| QR code scanned from another device | DISC-01/02 | Requires physical device | 1. Start server 2. Scan QR from phone 3. Verify page loads |
| File listing renders in browser | DISC-03 | Visual verification | 1. Open browser to server URL 2. Verify files display with name, size, date |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
