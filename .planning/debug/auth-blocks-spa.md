---
status: diagnosed
trigger: "Auth middleware blocks SPA static files and login page from unauthenticated users"
created: 2026-03-11T00:00:00Z
updated: 2026-03-11T00:00:00Z
---

## Current Focus

hypothesis: AuthMiddleware EXEMPT_PREFIXES does not include the root path or SPA catch-all routes, so index.html is never served to unauthenticated users
test: Trace request for "/" through middleware exempt check
expecting: "/" does not match any of ("/api/auth/login", "/api/server-info", "/assets", "/share")
next_action: Report root cause

## Symptoms

expected: Unauthenticated users see the LoginPage component (React SPA)
actual: Browser shows {"detail": "Not authenticated"} (401 JSON from middleware)
errors: 401 on every non-exempt path including root
reproduction: Start server with --password mypass, visit root URL in browser
started: When auth middleware was added

## Eliminated

(none needed -- root cause identified on first hypothesis)

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

root_cause: AuthMiddleware.EXEMPT_PREFIXES on line 19 of auth_middleware.py does not exempt the SPA catch-all routes. The root path "/" (which serves index.html) is blocked by the middleware before the React app can load and show LoginPage.
fix: (not yet applied)
verification: (not yet done)
files_changed: []
