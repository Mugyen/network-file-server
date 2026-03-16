---
phase: 8
slug: tunnel-protocol
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3+ with pytest-asyncio 0.25+ |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| **Quick run command** | `uv run pytest tests/tunnel/ -x -q` |
| **Full suite command** | `uv run pytest server/tests/ tests/tunnel/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/tunnel/ -x -q`
- **After every plan wave:** Run `uv run pytest server/tests/ tests/tunnel/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | TUNL-01 | unit | `uv run pytest tests/tunnel/test_frames.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 0 | TUNL-02 | unit | `uv run pytest tests/tunnel/test_connection.py -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 0 | TUNL-03 | unit | `uv run pytest tests/tunnel/test_connection.py::test_backpressure_blocks -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 0 | TUNL-04 | unit | `uv run pytest tests/tunnel/test_connection.py::test_control_messages_are_text -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/tunnel/__init__.py` — empty, makes directory a package
- [ ] `tests/tunnel/conftest.py` — `MockWebSocket` fixture and shared test helpers
- [ ] `tests/tunnel/test_frames.py` — stubs for TUNL-01 (serialization round-trip, reject short, reject oversized)
- [ ] `tests/tunnel/test_connection.py` — stubs for TUNL-02, TUNL-03, TUNL-04
- [ ] Update `pyproject.toml` `testpaths` to include `tests/tunnel`
- [ ] `tunnel/__init__.py` — public API re-exports
- [ ] `tunnel/constants.py` — all protocol constants
- [ ] `tunnel/enums.py` — FrameType enum
- [ ] `tunnel/frames.py` — serialize/deserialize functions
- [ ] `tunnel/connection.py` — TunnelConnection class
- [ ] `tunnel/exceptions.py` — typed exception hierarchy

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
