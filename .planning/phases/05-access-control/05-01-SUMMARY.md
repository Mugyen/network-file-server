---
phase: 05-access-control
plan: 01
subsystem: auth
tags: [bcrypt, itsdangerous, cli, session-tokens, access-control]

# Dependency graph
requires: []
provides:
  - "--password, --read-only, --receive CLI flags with validation"
  - "ServerConfig with password_hash, read_only, receive fields"
  - "AuthTokenService for signed session token create/validate"
  - "hash_password and verify_password bcrypt utilities"
  - "AccessDeniedError and ReadOnlyError exception types"
  - "Test fixtures for password, read-only, receive app modes"
affects: [05-access-control]

# Tech tracking
tech-stack:
  added: [bcrypt, itsdangerous]
  patterns: [module-level get/set singleton for AuthTokenService, create_default_config factory]

key-files:
  created:
    - server/app/services/auth_service.py
    - server/tests/test_auth_service.py
  modified:
    - server/app/cli.py
    - server/app/config.py
    - server/app/exceptions.py
    - server/tests/conftest.py
    - server/tests/test_cli.py
    - server/tests/test_config.py

key-decisions:
  - "Used create_default_config factory to avoid breaking existing callers of ServerConfig"
  - "Executed Task 2 (auth service) before Task 1 (CLI) since CLI imports from auth service"

patterns-established:
  - "Module-level get/set_token_service singleton pattern matching config.py"
  - "create_default_config factory for common no-auth ServerConfig construction"

requirements-completed: [AUTH-01, AUTH-03, AUTH-08]

# Metrics
duration: 5min
completed: 2026-03-10
---

# Phase 5 Plan 1: CLI Flags, Config, and Auth Service Summary

**bcrypt password hashing, itsdangerous session tokens, CLI --password/--read-only/--receive flags with mutual exclusion validation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-09T21:03:14Z
- **Completed:** 2026-03-09T21:07:47Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- Auth token service with bcrypt password hashing/verification and itsdangerous signed session tokens
- CLI extended with --password, --read-only, --receive flags with mutual exclusion and 72-byte limit validation
- ServerConfig extended with password_hash, read_only, receive fields; create_default_config factory added
- AccessDeniedError and ReadOnlyError exception types added
- Comprehensive test fixtures for all access modes ready for Plan 02 consumption
- All 244 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 2: Auth token service** (RED) - `216c39d` (test)
2. **Task 2: Auth token service** (GREEN) - `0e6edcb` (feat)
3. **Task 1: CLI flags, config, exceptions** (RED) - `e320fc1` (test)
4. **Task 1: CLI flags, config, exceptions** (GREEN) - `9392de7` (feat)

_Note: Task 2 executed before Task 1 because CLI imports from auth service._

## Files Created/Modified
- `server/app/services/auth_service.py` - Password hashing, verification, AuthTokenService with itsdangerous
- `server/app/cli.py` - Added --password, --read-only, --receive flags with validation and token service setup
- `server/app/config.py` - Extended ServerConfig with access control fields, added create_default_config
- `server/app/exceptions.py` - Added AccessDeniedError and ReadOnlyError
- `server/tests/conftest.py` - Added fixtures for password, read-only, receive app modes
- `server/tests/test_auth_service.py` - 15 tests for auth service
- `server/tests/test_cli.py` - Added 9 tests for new CLI flags and validation
- `server/tests/test_config.py` - Added 7 tests for config extension and exceptions

## Decisions Made
- Executed Task 2 before Task 1 to satisfy import dependency (CLI imports AuthTokenService)
- Used create_default_config factory to minimize changes in existing test files that construct ServerConfig

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ServerConfig constructor breakage in 5 test files**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Extending ServerConfig with 3 new required positional args broke 5 test files using old 2-arg constructor
- **Fix:** Updated test_clipboard_service, test_file_request_service, test_websocket, test_spa_serving to use create_default_config; updated test_routes_info with explicit args
- **Files modified:** server/tests/test_clipboard_service.py, server/tests/test_file_request_service.py, server/tests/test_websocket.py, server/tests/test_spa_serving.py, server/tests/test_routes_info.py
- **Verification:** Full test suite 244/244 pass
- **Committed in:** 9392de7 (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary fix for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth service, config, CLI flags, and exceptions are ready for Plan 02 (middleware)
- Test fixtures for all modes available in conftest.py
- No blockers

---
*Phase: 05-access-control*
*Completed: 2026-03-10*
