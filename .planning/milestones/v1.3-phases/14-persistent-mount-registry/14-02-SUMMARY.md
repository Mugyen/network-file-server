---
phase: 14-persistent-mount-registry
plan: 02
subsystem: database
tags: [sqlite, aiosqlite, persistence, async, mount-registry, reclaim, ttl-sweep, test-migration]

requires:
  - phase: 14-persistent-mount-registry
    provides: SqliteMountRegistry class with full async API, ReclaimResult, RelayConfig.db_path

provides:
  - SqliteMountRegistry wired into FastAPI lifespan as the sole registry
  - Agent reconnect/reclaim logic in agent_ws.py with IP-matched OFFLINE mount recovery
  - TTL sweep with expire() for status transition and delete_expired_before() for retention cleanup
  - Health endpoint using public mount_count() method
  - All relay tests migrated to async SqliteMountRegistry with in-memory SQLite

affects: [15-ux-polish, cloud-run-deployment]

tech-stack:
  added: []
  patterns: [async-lifespan-registry-init, manual-registry-setup-for-test-ws-transport, reclaim-aware-mount-registration]

key-files:
  created: []
  modified:
    - relay/app/main.py
    - relay/app/routers/agent_ws.py
    - relay/app/services/ttl_sweep.py
    - relay/app/routers/health.py
    - relay/app/routers/mount_proxy.py
    - relay/app/services/sqlite_registry.py
    - tests/relay/conftest.py
    - tests/relay/test_agent_ws.py
    - tests/relay/test_ttl.py
    - tests/relay/test_health.py
    - tests/relay/test_mount_proxy.py
    - tests/relay/test_mount_cap.py
    - tests/relay/test_rate_limit.py
    - docs/project-log.md

key-decisions:
  - "httpx.ASGITransport does not trigger FastAPI lifespan -- all test fixtures pre-create SqliteMountRegistry manually via _setup_in_memory_registry()"
  - "mount_proxy.py get_connection() calls need await -- auto-fixed as blocking Rule 3 deviation"
  - "mount_count() method added to SqliteMountRegistry for health endpoint (replaces private _mounts dict access)"

patterns-established:
  - "Test registry setup: _setup_in_memory_registry() creates in-memory SQLite and installs as global singleton"
  - "Reclaim-aware registration: try_reclaim first, then has_mount check, then generate fresh code"
  - "Lifespan owns registry lifecycle: create on startup, close on shutdown"

requirements-completed: [PERS-01, PERS-02, PERS-03, PERS-04]

duration: 14min
completed: 2026-03-30
---

# Phase 14 Plan 02: Lifespan Integration Summary

**SqliteMountRegistry wired into relay lifespan with agent reclaim logic, TTL sweep retention cleanup, and full test suite migration to async**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-30T12:11:50Z
- **Completed:** 2026-03-30T12:26:16Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- SqliteMountRegistry is now the sole registry used by the running relay application, created in lifespan and closed on shutdown
- Agent disconnect marks mount OFFLINE (not deleted), enabling reconnect/reclaim within TTL window
- Agent reconnecting with preferred code reclaims OFFLINE mount if IP matches, response includes reclaimed=true and remaining_ttl
- TTL sweep calls expire() for status transition (retains record) and delete_expired_before() for 6h retention cleanup
- All 166 relay tests pass with SqliteMountRegistry as the backing store (320 total project tests green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire SqliteMountRegistry into lifespan, agent_ws reclaim, ttl_sweep retention, and health** - `8459493` (feat)
2. **Task 2: Migrate existing tests to async SqliteMountRegistry** - `a7cbca3` (feat)

## Files Created/Modified
- `relay/app/main.py` - Lifespan creates SqliteMountRegistry from config.db_path, removes sync MountRegistry() creation
- `relay/app/routers/agent_ws.py` - Reclaim-aware code assignment, time.time() timestamps, mark_offline on disconnect, await on all registry calls
- `relay/app/services/ttl_sweep.py` - Uses SqliteMountRegistry type, time.time(), expire() for TTL expiry, delete_expired_before for retention
- `relay/app/routers/health.py` - Uses public mount_count() method instead of private _mounts dict
- `relay/app/routers/mount_proxy.py` - Added await to get_connection() calls (now async)
- `relay/app/services/sqlite_registry.py` - Added mount_count() method for health endpoint
- `tests/relay/conftest.py` - _setup_in_memory_registry() factory, async relay_app fixture, async registered_relay_client
- `tests/relay/test_agent_ws.py` - Reclaim tests, disconnect marks OFFLINE test, mount_registered includes reclaimed field
- `tests/relay/test_ttl.py` - SqliteMountRegistry unit tests with retention cleanup test
- `tests/relay/test_health.py` - Async mount_count() calls
- `tests/relay/test_mount_proxy.py` - Async get_connection(), pre-created registry for WS proxy tests
- `tests/relay/test_mount_cap.py` - Async prefill and expire via registry methods
- `tests/relay/test_rate_limit.py` - Async app factory with in-memory registry
- `docs/project-log.md` - Phase 14 completion summary

## Decisions Made
- httpx.ASGITransport does not trigger FastAPI lifespan events, so all test fixtures pre-create SqliteMountRegistry manually via _setup_in_memory_registry()
- Added mount_count() to SqliteMountRegistry (SELECT COUNT(*) FROM mounts) for health endpoint instead of accessing private _mounts dict
- mount_proxy.py needed await on get_connection() -- auto-fixed as blocking deviation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mount_proxy.py get_connection() needs await**
- **Found during:** Task 2 (test migration)
- **Issue:** mount_proxy.py calls `get_registry().get_connection(code)` synchronously, but get_connection is now async on SqliteMountRegistry
- **Fix:** Added `await` to both get_connection() call sites in mount_proxy.py (HTTP proxy and WS proxy)
- **Files modified:** relay/app/routers/mount_proxy.py
- **Verification:** Full test suite passes (320 tests green)
- **Committed in:** a7cbca3 (Task 2 commit)

**2. [Rule 3 - Blocking] httpx.ASGITransport does not trigger lifespan**
- **Found during:** Task 2 (test migration)
- **Issue:** Tests using httpx.ASGITransport and ASGIWebSocketTransport do not trigger FastAPI lifespan events, so the SqliteMountRegistry is never created
- **Fix:** Created _setup_in_memory_registry() helper that manually creates an in-memory SqliteMountRegistry and installs it as the global singleton. All test fixtures use this instead of relying on lifespan.
- **Files modified:** tests/relay/conftest.py, all test files
- **Verification:** All 166 relay tests pass
- **Committed in:** a7cbca3 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes necessary for the async migration to work. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 14 (Persistent Mount Registry) is complete -- all 4 PERS requirements satisfied
- Phase 15 (UX Polish and Drop Box) can proceed -- it depends on Phase 14 for persistent mounts
- The relay is now fully SQLite-backed: mounts survive restarts, agents reclaim codes, expired records are cleaned up

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 14-persistent-mount-registry*
*Completed: 2026-03-30*
