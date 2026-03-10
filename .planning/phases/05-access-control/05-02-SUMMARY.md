---
phase: 05-access-control
plan: 02
subsystem: auth
tags: [asgi-middleware, session-cookie, read-only, receive-mode, route-guards]

# Dependency graph
requires:
  - phase: 05-access-control-01
    provides: "AuthTokenService, ServerConfig with access control fields, hash/verify password, test fixtures"
provides:
  - "Pure ASGI AuthMiddleware for cookie-based session gating"
  - "POST /api/auth/login and /api/auth/logout endpoints"
  - "Read-only mode guards on all 10 write surfaces + WebSocket snippet_update"
  - "Receive-mode API restrictions (only upload, server-info, auth accessible)"
  - "Extended server-info with read_only, receive, password_required, hostname"
  - "LoginRequest schema"
affects: [05-access-control]

# Tech tracking
tech-stack:
  added: [httpx-ws]
  patterns: [pure ASGI middleware for auth gating, FastAPI Depends for mode guards, exception handler pattern for access control errors]

key-files:
  created:
    - server/app/middleware/__init__.py
    - server/app/middleware/auth_middleware.py
    - server/app/middleware/mode_guard.py
    - server/app/routers/auth.py
    - server/tests/test_auth.py
    - server/tests/test_read_only.py
    - server/tests/test_receive_mode.py
  modified:
    - server/app/main.py
    - server/app/models/schemas.py
    - server/app/routers/server_info.py
    - server/app/routers/files.py
    - server/app/routers/clipboard.py
    - server/app/routers/file_requests.py
    - server/app/routers/websocket.py

key-decisions:
  - "Used pure ASGI middleware (not BaseHTTPMiddleware) for auth gating to avoid deprecation"
  - "WebSocket auth: accept then close(4001) since ASGI middleware cannot reject before upgrade"
  - "Separate require_write_access and require_full_access guards for orthogonal mode enforcement"

patterns-established:
  - "Pure ASGI middleware pattern for request-level gating"
  - "Depends() route dependencies for mode-specific access control"
  - "Exception handlers on app for custom error types -> 403 JSON responses"

requirements-completed: [AUTH-02, AUTH-04, AUTH-06]

# Metrics
duration: 8min
completed: 2026-03-10
---

# Phase 5 Plan 2: Auth Middleware, Route Guards, and Mode Restrictions Summary

**Pure ASGI auth middleware with cookie session gating, read-only write guards on all 10 write surfaces, and receive-mode API restrictions allowing only upload/server-info/auth**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-09T21:10:17Z
- **Completed:** 2026-03-09T21:18:39Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Auth middleware blocks unauthenticated HTTP requests on password-protected servers with 401
- Login endpoint verifies password via bcrypt and sets httpOnly session cookie
- All 10 write endpoints return 403 in read-only mode; reads and downloads still work
- Receive mode restricts API to only upload, server-info, and auth endpoints
- WebSocket auth enforced (accept + close 4001 for unauthenticated)
- server-info extended with read_only, receive, password_required, hostname
- 37 new integration tests, 281 total passing with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Auth middleware, login, server-info** (RED) - `ffbd728` (test)
2. **Task 1: Auth middleware, login, server-info** (GREEN) - `80446ab` (feat)
3. **Task 2: Read-only guards, receive-mode** (RED) - `7719250` (test)
4. **Task 2: Read-only guards, receive-mode** (GREEN) - `610be8d` (feat)

## Files Created/Modified
- `server/app/middleware/auth_middleware.py` - Pure ASGI middleware for cookie-based auth gating
- `server/app/middleware/mode_guard.py` - require_write_access and require_full_access dependencies
- `server/app/routers/auth.py` - POST /api/auth/login and /api/auth/logout endpoints
- `server/app/main.py` - Auth middleware registration, exception handlers for access control
- `server/app/models/schemas.py` - LoginRequest schema, extended ServerInfo with mode fields
- `server/app/routers/server_info.py` - Added read_only, receive, password_required, hostname
- `server/app/routers/files.py` - Added write and full-access guards to all endpoints
- `server/app/routers/clipboard.py` - Added write and full-access guards to all endpoints
- `server/app/routers/file_requests.py` - Added write and full-access guards to all endpoints
- `server/app/routers/websocket.py` - Auth check on connect, read-only snippet_update ignore
- `server/tests/test_auth.py` - 14 auth integration tests
- `server/tests/test_read_only.py` - 13 read-only mode tests
- `server/tests/test_receive_mode.py` - 10 receive mode tests

## Decisions Made
- Used pure ASGI middleware (not deprecated BaseHTTPMiddleware) for auth gating
- WebSocket auth: accept then close(4001) since ASGI middleware cannot reliably reject WebSocket before upgrade
- Separate require_write_access and require_full_access as orthogonal guards -- write guard only on write endpoints, full-access guard on all non-upload endpoints

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth middleware, route guards, and mode restrictions fully wired
- All access control enforcement in place for Plan 03 (frontend integration)
- No blockers

---
*Phase: 05-access-control*
*Completed: 2026-03-10*
