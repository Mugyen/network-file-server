---
phase: 13-abuse-prevention
plan: 02
subsystem: infra
tags: [ttl-enforcement, rate-limiting, limits-library, asyncio-sweep, websocket, abuse-prevention]

requires:
  - phase: 13-abuse-prevention
    provides: "RelayConfig, MountRecord with agent_ip/created_at/expires_at, count_mounts_by_ip(), active_mounts()"
provides:
  - "TTL background sweep with expiry warnings"
  - "Mount registration rate limiting via limits library on WebSocket endpoint"
  - "Per-IP mount cap enforcement with structured error messages"
affects: [14-persistent-mount-registry]

tech-stack:
  added: []
  patterns: [limits-library-direct-for-websocket-rate-limiting, asyncio-background-sweep-via-lifespan, ttl-warning-control-messages]

key-files:
  created:
    - relay/app/services/ttl_sweep.py
    - tests/relay/test_ttl.py
    - tests/relay/test_mount_cap.py
  modified:
    - relay/app/routers/agent_ws.py
    - relay/app/services/mount_registry.py
    - relay/app/main.py
    - tests/relay/test_rate_limit.py
    - docs/project-log.md

key-decisions:
  - "Use limits library directly for WebSocket rate limiting (SlowAPI decorators do not work on WebSocket endpoints)"
  - "TTL sweep split into sweep_once() for testability and run_ttl_sweep() for background loop"
  - "Rate limit and mount cap checks run before WebSocket accept, error sent after accept (WebSocket must be accepted before sending messages)"
  - "ttl_warned boolean field on MountRecord prevents duplicate warnings"

patterns-established:
  - "WebSocket rate limiting pattern: use limits library directly with test() + hit() instead of SlowAPI decorator"
  - "Background sweep pattern: asyncio.create_task in lifespan, sweep_once() for testable single-iteration logic"
  - "reset_mount_reg_limiter() function for test isolation of module-level rate limiter state"

requirements-completed: [ABUSE-01, ABUSE-03, ABUSE-04]

duration: 7min
completed: 2026-03-18
---

# Phase 13 Plan 02: TTL Enforcement, Background Sweep, Per-IP Mount Cap, and Mount Registration Rate Limiting Summary

**Mount TTL enforcement with asyncio background sweep and expiry warnings, per-IP concurrent mount cap (default 5), and mount registration rate limiting via limits library directly on WebSocket endpoint**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-17T18:41:59Z
- **Completed:** 2026-03-17T18:49:48Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- TTL enforcement: agent WebSocket accepts optional `ttl` query param, capped to config maximum (default 24h), background sweep expires mounts and closes connections
- TTL warning: sweep sends `{"type": "ttl_warning", "expires_in": N}` control message before expiry (configurable window, default 5min)
- Per-IP mount cap: rejects 6th concurrent mount from same IP with structured JSON error and WebSocket close code 1008
- Mount registration rate limiting: uses `limits` library directly (not SlowAPI) with MovingWindowRateLimiter on WebSocket endpoint
- All 612 project tests pass, 16 new tests added (10 TTL + 4 mount cap + 2 mount reg rate limit)

## Task Commits

Each task was committed atomically:

1. **Task 1: TTL enforcement, background sweep** - `787919b` (feat)
2. **Task 2: Per-IP mount cap and mount registration rate limiting** - `7c1113e` (feat)

## Files Created/Modified
- `relay/app/services/ttl_sweep.py` - Background TTL sweep with sweep_once() and run_ttl_sweep() coroutines
- `relay/app/routers/agent_ws.py` - Added ttl param, rate limit check, mount cap check, structured error responses
- `relay/app/services/mount_registry.py` - Added ttl_warned field to MountRecord
- `relay/app/main.py` - Added FastAPI lifespan to start/stop TTL sweep background task
- `tests/relay/test_ttl.py` - 10 tests: TTL capping, sweep expiry, warnings, resilience, edge cases
- `tests/relay/test_mount_cap.py` - 4 tests: cap at limit, over cap rejection, different IP, expired frees slot
- `tests/relay/test_rate_limit.py` - Added 2 mount reg rate limit tests (under/over limit)
- `docs/project-log.md` - Updated with plan summary

## Decisions Made
- Used `limits` library directly for WebSocket mount registration rate limiting because SlowAPI decorators do not work on WebSocket endpoints (confirmed by research)
- Split TTL sweep into `sweep_once()` (testable single iteration) and `run_ttl_sweep()` (infinite loop wrapper) for clean unit testing
- Added `reset_mount_reg_limiter()` function to reinitialize module-level MemoryStorage for test isolation
- Rate limit and cap checks run before WebSocket accept; errors sent after accept (WebSocket protocol requires accept before sending messages)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All abuse prevention requirements complete (ABUSE-01 through ABUSE-05)
- Phase 13 fully complete, ready for Phase 14 (Persistent Mount Registry)
- TTL sweep and mount cap patterns available for Phase 14 to build on (SQLite persistence layer)

## Self-Check: PASSED

All 9 key files verified on disk. Both task commits (787919b, 7c1113e) verified in git log.

---
*Phase: 13-abuse-prevention*
*Completed: 2026-03-18*
