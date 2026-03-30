---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Productionize Friend Tier
status: In Progress
last_updated: "2026-03-30T12:26:16Z"
last_activity: 2026-03-30 — Completed Phase 14 (Persistent Mount Registry) — all PERS requirements satisfied
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 10
  completed_plans: 7
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Any device can instantly share files with zero setup — scan QR, drop files, done. Works on LAN or over the internet.
**Current focus:** v1.3 Productionize Friend Tier — Phase 15 next

## Current Position

Phase: 15 of 15 (UX Polish and Drop Box)
Plan: 1 of 4
Status: In Progress
Last activity: 2026-03-30 — Completed Phase 14 (Persistent Mount Registry) — all PERS requirements satisfied

Progress: [██████░░░░] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 6 (this milestone)
- Average duration: 8min
- Total execution time: 46min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 12 | 2 | 12min | 6min |
| 13 | 2 | 15min | 7min |
| 14 | 2 | 19min | 10min |

## Milestones Shipped

| Version | Name | Phases | Plans | Shipped |
|---------|------|--------|-------|---------|
| v1.0 | MVP | 1-4 | 13 | 2026-03-09 |
| v1.1 | Share & Access Control | 5-7 | 7 | 2026-03-11 |
| v1.2 | Remote Mounts | 8-11 | 11 | 2026-03-16 |

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table.

Key decisions for v1.3:
- Use `--max-instances=1` on Cloud Run — relay is stateful (WebSocket connections + in-memory rate limiter + SQLite)
- SQLite at `/tmp/mounts.db` with `journal_mode=DELETE` — avoids WAL corruption on GCS FUSE; accept mount code loss on redeploy
- Drop box as in-relay subprocess — avoids separate container; `asyncio.create_subprocess_exec` isolates event loop
- Connection status via REST polling (`GET /m/{code}/status` every 30s) — status changes are rare; second WebSocket channel is disproportionate
- [12-01] Used --legacy-peer-deps for npm ci in Dockerfile (pre-existing vitest peer dep conflict, dev-only)
- [12-01] README.md included in Docker context via .dockerignore exception (hatchling requires it for wheel build)
- [Phase 12]: SecureCookieMiddleware uses raw ASGI for streaming correctness; CORSMiddleware outer, SecureCookieMiddleware inner (Starlette LIFO)
- [Phase 12]: Dev CORS: wildcard without credentials (per CORS spec); Prod CORS: explicit origins with credentials
- [13-01] Config module: YAML defaults + env var overrides via load_config(); reuses RelayEnv from logging module
- [13-01] SlowAPI moving-window strategy with in-memory storage; rate limit decorator uses lambda for dynamic config
- [13-01] 429 handler content-negotiates: HTML for browsers, JSON for API clients
- [13-02] WebSocket rate limiting uses limits library directly (SlowAPI decorators don't work on WebSocket endpoints)
- [13-02] TTL sweep split into sweep_once() + run_ttl_sweep() for testability; wired via FastAPI lifespan
- [13-02] Rate limit and cap checks before WebSocket accept; errors sent after accept (protocol requirement)
- [14-01] Single aiosqlite connection (no pool) — sufficient for single-instance relay at 300 req/min
- [14-01] mark_offline() is a no-op for non-ONLINE mounts — race guard prevents late disconnect from undoing reclaim
- [14-01] expire() retains SQLite record for 6h retention window; deregister() deletes immediately
- [14-01] TYPE_CHECKING guard on circular import between mount_registry.py and sqlite_registry.py
- [14-02] httpx.ASGITransport does not trigger FastAPI lifespan -- test fixtures pre-create SqliteMountRegistry manually
- [14-02] mount_count() method on SqliteMountRegistry for health endpoint (replaces private _mounts dict access)

### Pending Todos

None.

### Blockers/Concerns

- [Phase 14]: RESOLVED — SQLite at /tmp/mounts.db with journal_mode=DELETE; accept mount code loss on redeploy
- [Phase 15]: Vite SPA asset paths vs mount proxy catch-all route conflict — verify with local `docker run` immediately after Phase 12 Dockerfile
- [Phase 15]: Drop box embedded agent implementation path (in-process task vs subprocess) — SIGTERM handling on Cloud Run needs validation
