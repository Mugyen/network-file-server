---
phase: 12-cloud-run-foundation
plan: 02
subsystem: infra
tags: [cors, cookies, security, middleware, cloud-run, https]

# Dependency graph
requires:
  - phase: 12-cloud-run-foundation
    provides: Dockerfile, health endpoint, RelayEnv enum, structured logging, CLI with proxy_headers
provides:
  - SecureCookieMiddleware for HTTPS cookie security behind Cloud Run TLS
  - Conditional CORS configuration (locked production, permissive dev)
  - Proxy header verification tests
affects: [13-abuse-prevention, 14-persistent-mount-registry, 15-ux-polish-and-drop-box]

# Tech tracking
tech-stack:
  added: []
  patterns: [asgi-middleware-cookie-stamping, conditional-cors-by-environment]

key-files:
  created:
    - relay/app/middleware/__init__.py
    - relay/app/middleware/secure_cookies.py
    - tests/relay/test_secure_cookies.py
    - tests/relay/test_cors.py
    - tests/relay/test_proxy_headers.py
  modified:
    - relay/app/main.py
    - docs/project-log.md

key-decisions:
  - "SecureCookieMiddleware uses raw ASGI (not BaseHTTPMiddleware) for correctness with streaming responses"
  - "SecureCookieMiddleware added first (inner), CORSMiddleware added second (outer, LIFO) so CORS handles preflight before anything else"
  - "Dev CORS uses wildcard without credentials (wildcard + credentials is invalid per CORS spec)"

patterns-established:
  - "Middleware ordering: SecureCookieMiddleware inner, CORSMiddleware outer (Starlette LIFO)"
  - "Environment-conditional middleware: read RELAY_ENV in create_relay_app(), branch on RelayEnv enum"
  - "Fail-fast in production: raise ValueError when required env vars missing"

requirements-completed: [DEPLOY-04, DEPLOY-05, DEPLOY-06]

# Metrics
duration: 5min
completed: 2026-03-16
---

# Phase 12 Plan 02: HTTPS Cookie Security, CORS Lockdown, and Proxy Header Verification Summary

**SecureCookieMiddleware stamps Secure flag behind HTTPS proxy; CORS locked to explicit origins with credentials in production; proxy_headers verified**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-16T17:46:00Z
- **Completed:** 2026-03-16T17:51:00Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- SecureCookieMiddleware (raw ASGI) stamps Secure flag on Set-Cookie when X-Forwarded-Proto is https
- Production CORS rejects unlisted origins, allows configured origins with credentials
- Dev CORS retains wildcard origins (no credentials) for local development
- Missing RELAY_ALLOWED_ORIGINS in production raises ValueError (fail-fast)
- Proxy header configuration verified (proxy_headers=True, forwarded_allow_ips="*")
- 15 new tests (7 secure cookies + 7 CORS + 1 proxy headers), 88 total relay tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: SecureCookieMiddleware (RED)** - `6ea4277` (test)
2. **Task 1: SecureCookieMiddleware (GREEN)** - `5337abe` (feat)
3. **Task 2: Conditional CORS and proxy headers (RED)** - `6310167` (test)
4. **Task 2: Conditional CORS and middleware wiring (GREEN)** - `e0a0cad` (feat)
5. **Docs update** - `0e07c92` (chore)

_Both tasks followed TDD (test -> feat). No refactor steps needed._

## Files Created/Modified
- `relay/app/middleware/__init__.py` - Package init for middleware module
- `relay/app/middleware/secure_cookies.py` - ASGI middleware stamping Secure on Set-Cookie behind HTTPS
- `relay/app/main.py` - Conditional CORS (production/dev), SecureCookieMiddleware wiring
- `tests/relay/test_secure_cookies.py` - 7 tests: Secure flag, no-double-stamp, passthrough, multiple cookies
- `tests/relay/test_cors.py` - 7 tests: wildcard dev, reject/allow prod origins, credentials, ValueError
- `tests/relay/test_proxy_headers.py` - 1 test: uvicorn.run receives proxy_headers=True
- `docs/project-log.md` - Project log entry

## Decisions Made
- Used raw ASGI middleware (not Starlette BaseHTTPMiddleware) for SecureCookieMiddleware to avoid issues with streaming responses
- SecureCookieMiddleware added first (inner), CORSMiddleware second (outer) -- Starlette LIFO ordering ensures CORS handles preflight before inner middleware processes cookies
- Dev CORS omits allow_credentials because wildcard + credentials is invalid per CORS spec

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 6 DEPLOY requirements (01-06) for Phase 12 are complete
- Relay container has: Dockerfile, health probe, structured logging, secure cookies, locked CORS, proxy headers
- Ready for Phase 13 (abuse prevention) to add rate limiting and connection limits
- Docker image builds and all 88 relay tests pass

## Self-Check: PASSED

All 5 created files verified present. All 5 commits verified in git log.

---
*Phase: 12-cloud-run-foundation*
*Completed: 2026-03-16*
