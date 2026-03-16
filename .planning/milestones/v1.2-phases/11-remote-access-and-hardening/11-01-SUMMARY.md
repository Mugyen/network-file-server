---
phase: 11-remote-access-and-hardening
plan: 01
subsystem: auth
tags: [bcrypt, argparse, asyncio, ttl, cookie, websocket]

requires:
  - phase: 10-agent-cli
    provides: connect_and_serve, run_agent_loop, agent/connection.py, agent/cli.py

provides:
  - "parse_duration(value: str) -> int — converts s/m/h/d strings to seconds"
  - "AgentExpiredError — typed exception for TTL-triggered exit (no reconnect)"
  - "ServerConfig.mount_code — field for remote mount isolation"
  - "Cookie path scoped to /m/{code}/ when mount_code is set"
  - "--password and --ttl flags on mount subcommand"
  - "TTL countdown timer in connect_and_serve with clean AgentExpiredError raise"
  - "run_agent_loop catches AgentExpiredError and exits without retry"

affects:
  - 11-02-PLAN
  - agent-cli
  - relay-auth

tech-stack:
  added: []
  patterns:
    - "parse_duration as argparse type= for human-readable durations"
    - "TTL countdown via asyncio.create_task + conn.close() + flag-then-raise pattern"
    - "AgentExpiredError as exit sentinel (not a connection error — no retry)"
    - "mount_code in ServerConfig for per-mount cookie path isolation"

key-files:
  created:
    - agent/duration.py
    - agent/exceptions.py
    - tests/agent/test_duration.py
    - tests/agent/test_cli_task2.py
    - tests/agent/test_agent_connection_task2.py
    - server/tests/test_config_mount_code.py
    - server/tests/test_auth_cookie_path.py
  modified:
    - server/app/config.py
    - server/app/routers/auth.py
    - server/app/middleware/auth_middleware.py
    - server/app/cli.py
    - agent/cli.py
    - agent/connection.py
    - tests/agent/test_agent_connection.py
    - tests/agent/test_cli.py
    - server/tests/conftest.py
    - server/tests/test_config.py
    - server/tests/test_routes_info.py
    - server/tests/test_share.py

key-decisions:
  - "parse_duration uses re.compile(r'^(\\d+)([smhd])$') pattern — strict format, no spaces allowed"
  - "AgentExpiredError has a message attribute alongside the Exception message for programmatic access"
  - "mount_code is a required positional parameter in ServerConfig.__init__ (no default) — all callers must pass explicitly to avoid silent omission bugs"
  - "TTL timer uses asyncio.create_task for _ttl_countdown; sets ttl_expired flag then calls conn.close(); after receive loop exits, checks flag and raises AgentExpiredError"
  - "/api/auth/logout added to auth middleware exempt paths — logout should work without a valid session cookie"
  - "connect_and_serve creates AuthTokenService and calls set_token_service when password_hash is not None, using secrets.token_hex(32) as the signing key"

requirements-completed:
  - ACCS-01
  - ACCS-02

duration: 10min
completed: 2026-03-11
---

# Phase 11 Plan 01: Password Protection and TTL Auto-Expiry Summary

**Mount password protection with bcrypt + scoped session cookies, plus TTL auto-expiry using asyncio task that raises AgentExpiredError to prevent reconnect**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-11T14:57:00Z
- **Completed:** 2026-03-11T15:07:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 19

## Accomplishments
- Duration parser (`parse_duration`) converts `30m`/`2h`/`1d`/`90s` to seconds with strict validation
- `AgentExpiredError` provides typed TTL exit signal; `run_agent_loop` catches it and exits without retrying
- `ServerConfig.mount_code` isolates sessions per mount; auth cookies scoped to `/m/{code}/`
- `--password` and `--ttl` flags added to mount subcommand; password hashed with bcrypt before passing to connection layer

## Task Commits

1. **Task 1: Duration parser, AgentExpiredError, ServerConfig.mount_code, cookie path scoping** - `e0e8cd2` (feat)
2. **Task 2: CLI flags, TTL timer, connect_and_serve extension, no-retry on expiry** - `fc16ea8` (feat)

## Files Created/Modified

- `agent/duration.py` - parse_duration with s/m/h/d unit support
- `agent/exceptions.py` - AgentExpiredError with message attribute
- `server/app/config.py` - Added mount_code field; all callers updated
- `server/app/routers/auth.py` - Cookie path scoped by mount_code in login and logout
- `server/app/middleware/auth_middleware.py` - Added /api/auth/logout to exempt paths
- `server/app/cli.py` - --password and --ttl flags on mount subcommand; imports parse_duration
- `agent/cli.py` - Password length validation, hash_password call, passes to run_agent_loop
- `agent/connection.py` - Extended connect_and_serve + run_agent_loop signatures; TTL timer; AuthTokenService setup

## Decisions Made

- `mount_code` is a required parameter in `ServerConfig.__init__` (no default) to prevent silent omission
- TTL uses a flag (`ttl_expired`) set by `_ttl_countdown` task; after receive loop exits the flag is checked and `AgentExpiredError` is raised — this avoids raising inside async context managers
- `/api/auth/logout` exempt from auth middleware (logout should always work regardless of session validity)
- `AuthTokenService` initialized in `connect_and_serve` when `password_hash` is not None using a per-connection `secrets.token_hex(32)` signing key

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added /api/auth/logout to auth middleware exempt paths**
- **Found during:** Task 1 (cookie path scoping tests)
- **Issue:** Logout was blocked by auth middleware when session cookie was invalid/missing — you should be able to log out without a valid session
- **Fix:** Added `/api/auth/logout` to `EXEMPT_API_PREFIXES` in `auth_middleware.py`
- **Files modified:** `server/app/middleware/auth_middleware.py`
- **Verification:** All auth cookie path tests pass; existing auth tests unaffected
- **Committed in:** e0e8cd2 (Task 1 commit)

**2. [Rule 1 - Bug] Updated existing test signatures for connect_and_serve and run_agent_loop**
- **Found during:** Task 2 (after extending function signatures)
- **Issue:** Existing tests in `test_agent_connection.py` and `test_cli.py` called old 4-param signature; tests failed with TypeError
- **Fix:** Updated all call sites to pass `password_hash=None, ttl_seconds=None` explicitly
- **Files modified:** `tests/agent/test_agent_connection.py`, `tests/agent/test_cli.py`
- **Verification:** 514 tests pass with no failures
- **Committed in:** fc16ea8 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Password and TTL infrastructure ready for Phase 11 Plan 02
- SPA base URL injection for remote mounts (needed so React app uses `/m/{code}/api/` prefix) is the remaining challenge flagged in CONTEXT.md
- All 514 tests pass with no regressions

---
*Phase: 11-remote-access-and-hardening*
*Completed: 2026-03-11*
