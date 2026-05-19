---
status: resolved
trigger: "Auth middleware blocks SPA static files and login page from unauthenticated users"
created: 2026-03-11T00:00:00Z
updated: 2026-03-30T00:00:00Z
---

## Current Focus

hypothesis: Original diagnosis was incorrect -- middleware already correctly gates only /api/* paths
test: Ran all 337 server tests + manual path trace through middleware logic
expecting: All paths work correctly
next_action: Resolve as false positive

## Symptoms

expected: Unauthenticated users see the LoginPage component (React SPA)
actual: Browser shows {"detail": "Not authenticated"} (401 JSON from middleware)
errors: 401 on every non-exempt path including root
reproduction: Start server with --password mypass, visit root URL in browser
started: When auth middleware was added

## Eliminated

- hypothesis: AuthMiddleware EXEMPT_PREFIXES does not include root path "/" or SPA catch-all
  evidence: |
    Middleware uses GUARDED_PREFIX = "/api/" and only gates paths starting with /api/.
    The check `if not path.startswith(GUARDED_PREFIX)` passes through all non-API paths
    including "/", "/assets/*", "/share/*". This has been the design since the first commit
    (b68b24c). All 337 tests pass. test_unauthenticated_spa_serves_html explicitly verifies
    GET / returns 200 on a password-protected server.
  timestamp: 2026-03-30

## Evidence

- timestamp: 2026-03-11
  checked: EXEMPT_PREFIXES in auth_middleware.py line 19
  found: Only exempts /api/auth/login, /api/server-info, /assets, /share
  implication: Root path "/" and SPA catch-all routes are NOT exempt

- timestamp: 2026-03-11
  checked: SPA mounting in main.py lines 88-111
  found: index.html served via catch-all "/{path:path}" route, assets via "/assets" mount
  implication: /assets/* files are exempt but index.html at "/" is blocked

- timestamp: 2026-03-11
  checked: Frontend flow in main.tsx
  found: Root component fetches /api/server-info first, then conditionally renders LoginPage
  implication: The SPA must load (index.html + JS) before LoginPage can render; both /api/server-info AND the SPA files must be accessible

## Resolution

root_cause: FALSE POSITIVE. The middleware was never broken. It uses GUARDED_PREFIX = "/api/" and only gates /api/* paths. Non-API paths (/, /assets/*, /share/*) always pass through. The original diagnosis confused EXEMPT_API_PREFIXES (which exempt specific /api/* routes) with the top-level GUARDED_PREFIX check (which lets all non-API paths through).
fix: No code change needed. The auth middleware is correctly implemented.
verification: All 337 server tests pass. test_unauthenticated_spa_serves_html confirms GET / returns 200 on password-protected server. Manual path tracing confirms all SPA routes pass through middleware.
files_changed: []
