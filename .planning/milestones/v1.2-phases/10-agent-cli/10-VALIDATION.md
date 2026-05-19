---
phase: 10
slug: agent-cli
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.0 + pytest-asyncio 0.25.0 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — asyncio_mode = "auto" |
| **Quick run command** | `uv run pytest tests/agent/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/agent/ tests/relay/test_agent_ws.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | relay change | unit | `uv run pytest tests/relay/test_agent_ws.py -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | AGNT-01 | unit | `uv run pytest tests/agent/test_cli.py -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | AGNT-01 | unit | `uv run pytest server/tests/test_cli.py -x` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 2 | AGNT-02 | unit | `uv run pytest tests/agent/test_proxy.py -x` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | AGNT-02 | unit | `uv run pytest tests/agent/test_proxy.py::test_cancel -x` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 2 | AGNT-02 | unit | `uv run pytest tests/agent/test_proxy.py::test_concurrent -x` | ❌ W0 | ⬜ pending |
| 10-02-04 | 02 | 2 | AGNT-03 | unit | `uv run pytest tests/agent/test_display.py -x` | ❌ W0 | ⬜ pending |
| 10-02-05 | 02 | 2 | AGNT-04 | unit | `uv run pytest tests/agent/test_connection.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/__init__.py` — test package init
- [ ] `tests/agent/conftest.py` — shared fixtures (MockTunnelConnection variant for agent-side, mock ASGI app)
- [ ] `tests/agent/test_cli.py` — stubs for AGNT-01 (mount subcommand parsing)
- [ ] `tests/agent/test_proxy.py` — stubs for AGNT-02 (request proxying, cancel, concurrent)
- [ ] `tests/agent/test_display.py` — stubs for AGNT-03 (URL, QR, mount code display)
- [ ] `tests/agent/test_connection.py` — stubs for AGNT-04 (backoff, reconnect, code preservation)
- [ ] `tests/relay/test_agent_ws.py` — updated stubs for relay protocol change (mount_registered message)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| QR code scannable by phone camera | AGNT-03 | Visual verification | Run `network-file-server mount ./test --server <url>`, scan QR with phone |
| Terminal output formatting | AGNT-03 | Visual layout check | Verify URL, code, status line display correctly in terminal |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
