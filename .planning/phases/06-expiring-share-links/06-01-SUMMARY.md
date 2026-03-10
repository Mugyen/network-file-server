---
phase: 06-expiring-share-links
plan: 01
subsystem: api
tags: [itsdangerous, jinja2, share-links, fastapi, templates]

requires:
  - phase: 05-access-control
    provides: AuthTokenService singleton pattern, auth middleware with EXEMPT_PREFIXES

provides:
  - ShareLinkService with create/validate/revoke/list and auto-expiry cleanup
  - Share router with 5 endpoints (POST/GET/DELETE /api/shares, GET /share/{token}, GET /share/{token}/download)
  - 3 standalone Jinja2 HTML templates for share link pages
  - ShareTTL enum with 4 TTL values
  - Auth middleware bypass for /share routes

affects: [06-02-frontend-share-ui]

tech-stack:
  added: [jinja2]
  patterns: [Jinja2 server-rendered pages alongside SPA, signed token with per-record TTL]

key-files:
  created:
    - server/app/services/share_service.py
    - server/app/routers/share.py
    - templates/share_download.html
    - templates/share_expired.html
    - templates/share_unavailable.html
    - server/tests/test_share_service.py
    - server/tests/test_share.py
  modified:
    - server/app/models/enums.py
    - server/app/models/schemas.py
    - server/app/middleware/auth_middleware.py
    - server/app/main.py
    - server/app/cli.py
    - pyproject.toml

key-decisions:
  - "Used Jinja2 server-rendered HTML for share pages (not React SPA) so recipients need no JS bundle"
  - "Dedicated SALT='share-link' separates share tokens from auth session tokens"
  - "ShareLinkService auto-initialized in create_app fallback if not already set (test-friendly)"

patterns-established:
  - "Jinja2 templates in project-root/templates/ for server-rendered pages"
  - "Per-record TTL enforcement via itsdangerous max_age parameter"

requirements-completed: [SHARE-01, SHARE-02, SHARE-03, SHARE-04, SHARE-05, SHARE-06, SHARE-07]

duration: 6min
completed: 2026-03-10
---

# Phase 6 Plan 1: Share Link Backend Summary

**ShareLinkService with signed expiring tokens, 5-endpoint share router, and 3 standalone Jinja2 HTML pages with dark mode support**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-09T21:47:53Z
- **Completed:** 2026-03-09T21:53:32Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- ShareLinkService with create, validate, revoke, list, and automatic expiry cleanup using itsdangerous URLSafeTimedSerializer
- Share router with POST/GET/DELETE /api/shares and GET /share/{token} + /share/{token}/download
- 3 standalone HTML templates (download page, expired page, unavailable page) with dark mode via prefers-color-scheme
- Auth middleware bypass for /share routes so share links work on password-protected servers
- 36 new tests (22 unit + 14 integration), full suite 317 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: ShareLinkService, enums, schemas, and unit tests (RED)** - `e420d4a` (test)
2. **Task 1: ShareLinkService, enums, schemas, and unit tests (GREEN)** - `4a97735` (feat)
3. **Task 2: Share router, templates, auth bypass, integration tests (RED)** - `93b70b2` (test)
4. **Task 2: Share router, templates, auth bypass, integration tests (GREEN)** - `366597f` (feat)
5. **Project log update** - `45fa893` (docs)

_Note: TDD tasks have separate RED and GREEN commits._

## Files Created/Modified
- `server/app/services/share_service.py` - ShareLinkService, ShareLinkRecord, 3 typed exceptions, singleton
- `server/app/routers/share.py` - Share router with 5 endpoints and Jinja2 template rendering
- `server/app/models/enums.py` - Added ShareTTL enum (900, 3600, 21600, 86400)
- `server/app/models/schemas.py` - Added CreateShareRequest and ShareLinkInfo Pydantic models
- `server/app/middleware/auth_middleware.py` - Added "/share" to EXEMPT_PREFIXES
- `server/app/main.py` - Share router registration and ShareLinkService auto-init
- `server/app/cli.py` - ShareLinkService initialization during CLI startup
- `templates/share_download.html` - Standalone download page with file info and Download button
- `templates/share_expired.html` - Expired/revoked link page
- `templates/share_unavailable.html` - File-deleted-after-sharing page
- `pyproject.toml` - Added jinja2 dependency
- `server/tests/test_share_service.py` - 22 unit tests for service, enum, schemas, singleton
- `server/tests/test_share.py` - 14 integration tests for all endpoints and auth bypass

## Decisions Made
- Used Jinja2 server-rendered HTML for share pages so recipients need no JS bundle or SPA
- Dedicated SALT="share-link" separates share tokens from auth session tokens (same serializer library)
- ShareLinkService auto-initialized in create_app if not already set, making test fixtures simpler
- Added jinja2 as a runtime dependency (previously not needed since SPA served static files)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed jinja2 dependency**
- **Found during:** Task 2 (Share router implementation)
- **Issue:** jinja2 not in project dependencies, required for Jinja2Templates
- **Fix:** Added `jinja2>=3.1.0` to pyproject.toml dependencies
- **Files modified:** pyproject.toml
- **Verification:** `uv run python -c "import jinja2"` succeeds
- **Committed in:** `4a97735` (Task 1 GREEN commit, added early)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for template rendering. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Share link backend fully operational, ready for frontend share UI (Plan 02)
- All 7 SHARE requirements have backend support
- Full test suite green (317 tests)

---
*Phase: 06-expiring-share-links*
*Completed: 2026-03-10*

## Self-Check: PASSED

All 7 created files verified. All 5 commit hashes verified.
