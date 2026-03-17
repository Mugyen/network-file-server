---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Productionize Friend Tier
status: executing
last_updated: "2026-03-18T18:49:48Z"
last_activity: 2026-03-18 — Completed 13-02 (TTL enforcement, mount cap, mount reg rate limiting)
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 9
  completed_plans: 4
  percent: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-16)

**Core value:** Any device can instantly share files with zero setup — scan QR, drop files, done. Works on LAN or over the internet.
**Current focus:** v1.3 Productionize Friend Tier — ready for Phase 14

## Current Position

Phase: 14 of 15 (Persistent Mount Registry)
Plan: 1 of 1
Status: Ready
Last activity: 2026-03-18 — Completed 13-02 (TTL enforcement, mount cap, mount reg rate limiting)

Progress: [████░░░░░░] 44%

## Performance Metrics

**Velocity:**
- Total plans completed: 4 (this milestone)
- Average duration: 7min
- Total execution time: 27min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 12 | 2 | 12min | 6min |
| 13 | 2 | 15min | 7min |

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

### Pending Todos

None.

### Blockers/Concerns

- [Phase 14]: GCS FUSE vs `/tmp` SQLite storage strategy — product decision needed before implementation (accept mount code loss on redeploy vs pay for `--min-instances=1`)
- [Phase 15]: Vite SPA asset paths vs mount proxy catch-all route conflict — verify with local `docker run` immediately after Phase 12 Dockerfile
- [Phase 15]: Drop box embedded agent implementation path (in-process task vs subprocess) — SIGTERM handling on Cloud Run needs validation
