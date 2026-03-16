---
phase: 11
slug: remote-access-and-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + vitest (frontend) |
| **Config file** | pyproject.toml, client/vitest.config.ts |
| **Quick run command** | `uv run pytest tests/agent/ tests/tunnel/ tests/relay/ -x -q --timeout=10` |
| **Full suite command** | `uv run pytest tests/ -x -q --timeout=30 && cd client && npx vitest run` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/agent/ tests/tunnel/ tests/relay/ -x -q --timeout=10`
- **After every plan wave:** Run `uv run pytest tests/ -x -q --timeout=30 && cd client && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | ACCS-01 | unit | `uv run pytest tests/agent/test_password_mount.py -x -q` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | ACCS-02 | unit | `uv run pytest tests/agent/test_ttl_expiry.py -x -q` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | ACCS-01 | unit | `uv run pytest tests/test_cookie_scoping.py -x -q` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 2 | RMUI-01 | unit | `cd client && npx vitest run src/utils/remoteMount.test.ts` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 2 | RMUI-02 | unit | `uv run pytest tests/tunnel/test_ws_frames.py -x -q` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 | 2 | RMUI-02 | unit | `uv run pytest tests/relay/test_ws_proxy.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/agent/test_password_mount.py` — stubs for ACCS-01 password passthrough
- [ ] `tests/agent/test_ttl_expiry.py` — stubs for ACCS-02 TTL timer and clean exit
- [ ] `tests/test_cookie_scoping.py` — stubs for ACCS-01 cookie path scoping
- [ ] `client/src/utils/remoteMount.test.ts` — stubs for RMUI-01 URL detection
- [ ] `tests/tunnel/test_ws_frames.py` — stubs for RMUI-02 WS frame types
- [ ] `tests/relay/test_ws_proxy.py` — stubs for RMUI-02 WS upgrade proxying

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SPA renders login page at /m/{code}/ | ACCS-01 | Browser rendering | Open relay URL with password mount, verify login form appears |
| TTL countdown display in terminal | ACCS-02 | Terminal output visual | Run mount with --ttl 1m, watch terminal countdown |
| "Remote" badge visible in header | RMUI-01 | Visual UI check | Access mount via relay, verify badge appears |
| Clipboard sync works through relay | RMUI-02 | End-to-end WS flow | Copy text in SPA via relay, verify sync |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
