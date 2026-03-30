---
phase: 14-persistent-mount-registry
plan: 01
subsystem: database
tags: [sqlite, aiosqlite, persistence, async, mount-registry]

requires:
  - phase: 13-abuse-prevention
    provides: MountRecord with agent_ip/created_at/expires_at, RelayConfig, MountStatus enum

provides:
  - SqliteMountRegistry class with full async API (register, deregister, get_connection, mark_offline, expire, try_reclaim, active_mounts, etc.)
  - ReclaimResult frozen dataclass for mount reclaim responses
  - RelayConfig.db_path field with YAML default and RELAY_DB_PATH env override
  - aiosqlite dependency installed

affects: [14-02-lifespan-integration, ttl-sweep, agent-ws-reclaim]

tech-stack:
  added: [aiosqlite 0.22.1]
  patterns: [async-factory-classmethod, sqlite-source-of-truth-with-memory-connections, typed-exceptions-for-lifecycle-violations]

key-files:
  created:
    - relay/app/services/sqlite_registry.py
    - tests/relay/test_sqlite_registry.py
  modified:
    - relay/app/config.py
    - relay/config.yaml
    - relay/app/services/mount_registry.py
    - pyproject.toml
    - tests/relay/test_ttl.py

key-decisions:
  - "Single aiosqlite connection (no pool) -- sufficient for single-instance relay at 300 req/min"
  - "mark_offline() is a no-op for non-ONLINE mounts -- race guard prevents late disconnect from undoing reclaim"
  - "expire() retains SQLite record for 6h retention window, unlike deregister() which deletes immediately"
  - "TYPE_CHECKING guard on circular import between mount_registry.py and sqlite_registry.py"

patterns-established:
  - "Async factory: SqliteMountRegistry.create() classmethod for async init (aiosqlite.connect + schema + cleanup)"
  - "Dual storage: SQLite for metadata persistence, in-memory dict for live TunnelConnection objects"
  - "Startup cleanup sequence: delete stale expired > mark newly-expired > mark online as offline"

requirements-completed: [PERS-01, PERS-02, PERS-04]

duration: 5min
completed: 2026-03-30
---

# Phase 14 Plan 01: SqliteMountRegistry Summary

**SQLite-backed mount registry with async CRUD, startup cleanup, reclaim, and retention deletion using aiosqlite**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T12:02:34Z
- **Completed:** 2026-03-30T12:07:48Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 7

## Accomplishments
- SqliteMountRegistry class with all async methods matching MountRegistry interface plus expire(), try_reclaim(), delete_expired_before()
- Startup cleanup marks ONLINE as OFFLINE, expires past-due mounts, deletes records beyond 6h retention
- RelayConfig.db_path field loaded from YAML with RELAY_DB_PATH env override
- 39 comprehensive unit tests covering PERS-01 (persistence), PERS-02 (startup cleanup), PERS-04 (retention deletion), full CRUD, reclaim, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for SqliteMountRegistry** - `b7f75d8` (test)
2. **Task 1 GREEN: SqliteMountRegistry implementation** - `a39b9de` (feat)

_TDD task with RED (failing tests) and GREEN (implementation) commits._

## Files Created/Modified
- `relay/app/services/sqlite_registry.py` - SqliteMountRegistry class with full async API, ReclaimResult dataclass
- `tests/relay/test_sqlite_registry.py` - 39 unit tests covering all behaviors
- `relay/app/config.py` - Added db_path field to RelayConfig with YAML + env var loading
- `relay/config.yaml` - Added db_path default value (/tmp/mounts.db)
- `relay/app/services/mount_registry.py` - Singleton type annotations updated for SqliteMountRegistry
- `pyproject.toml` - Added aiosqlite dependency
- `tests/relay/test_ttl.py` - Fixed _make_test_config for new db_path field

## Decisions Made
- Single aiosqlite connection (no pool) -- sufficient for single-instance relay at 300 req/min
- mark_offline() is a no-op for non-ONLINE mounts (race guard per research open question 1)
- expire() retains SQLite record for retention window, distinct from deregister() which deletes
- Used TYPE_CHECKING guard to avoid circular import between mount_registry.py and sqlite_registry.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed test_ttl.py for new db_path field**
- **Found during:** Task 1 GREEN (verification)
- **Issue:** _make_test_config() in test_ttl.py constructed RelayConfig without the new db_path field, causing TypeError
- **Fix:** Added db_path="/tmp/test_mounts.db" to the test helper
- **Files modified:** tests/relay/test_ttl.py
- **Verification:** Full relay test suite (163 tests) passes
- **Committed in:** a39b9de (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minimal -- direct consequence of adding db_path to RelayConfig. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SqliteMountRegistry is ready for integration in plan 14-02
- Plan 14-02 will wire SqliteMountRegistry into the app factory lifespan, update agent_ws.py with reclaim logic, extend TTL sweep for retention cleanup, and migrate existing tests to async

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 14-persistent-mount-registry*
*Completed: 2026-03-30*
