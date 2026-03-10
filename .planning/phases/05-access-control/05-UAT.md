---
status: diagnosed
phase: 05-access-control
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md]
started: 2026-03-11T00:00:00Z
updated: 2026-03-11T00:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Run `uv run python -m server.app.cli .` (no flags). Server boots without errors and the web UI loads in browser showing the file list.
result: pass

### 2. Password-Protected Server Login
expected: Start server with `uv run python -m server.app.cli --password mypass .`. Browser shows a login page (not the file list). Enter wrong password → error message shown. Enter correct password → redirected to file list. Refreshing the page keeps you logged in (session cookie).
result: issue
reported: "I don't see a login page. It just starts directly as {\"detail\": \"Not authenticated\"}"
severity: major

### 3. Read-Only Mode — Write Controls Hidden
expected: Start server with `uv run python -m server.app.cli --read-only .`. File list loads normally. Upload button, delete button, rename option, create folder, file requests, and scratchpad controls are all hidden/absent. An amber "Read Only" badge appears in the header.
result: pass

### 4. Read-Only Mode — Downloads Still Work
expected: While in read-only mode, clicking a file downloads it successfully. Browsing folders works normally.
result: pass

### 5. Receive Mode — Drop Box Page
expected: Start server with `uv run python -m server.app.cli --receive .`. Browser shows a dedicated drop-box page (not the file list) with a centered drop zone. Drag-and-drop or file picker uploads work. Uploaded files appear in an inline success list. No file browsing or download is available.
result: pass

### 6. Password + Read-Only Combined
expected: Start server with `uv run python -m server.app.cli --password mypass --read-only .`. Login page appears first. After login, file list shows with read-only restrictions (no write controls, "Read Only" badge visible, "Protected" badge with lock icon visible).
result: issue
reported: "same issue, I don't see a login page at all"
severity: major

### 7. Logout
expected: While logged into a password-protected server, there should be a way to log out. After logging out, you are returned to the login page and cannot access the file list without re-entering the password.
result: skipped
reason: Blocked by login page issue — can't log in to test logout

### 8. CLI Startup Banner
expected: Start server with `uv run python -m server.app.cli --password mypass --read-only .`. The terminal output shows the active modes (password-protected, read-only) in the startup banner.
result: pass

## Summary

total: 8
passed: 5
issues: 2
pending: 0
skipped: 1

## Gaps

- truth: "Password-protected server shows login page for unauthenticated users"
  status: fixed
  reason: "User reported: I don't see a login page. It just starts directly as {\"detail\": \"Not authenticated\"}"
  severity: major
  test: 2
  root_cause: "AuthMiddleware EXEMPT_PREFIXES didn't include SPA routes — index.html was blocked, so React LoginPage never loaded"
  artifacts:
    - path: "server/app/middleware/auth_middleware.py"
      issue: "EXEMPT_PREFIXES gated all paths including SPA; should only gate /api/* paths"
  missing:
    - "Invert middleware logic: only gate /api/* paths, let all non-API paths through"
  debug_session: ".planning/debug/auth-blocks-spa.md"

- truth: "Password + read-only combined shows login page first, then read-only file list"
  status: fixed
  reason: "User reported: same issue, I don't see a login page at all"
  severity: major
  test: 6
  root_cause: "Same root cause as test 2 — AuthMiddleware blocked SPA HTML shell"
  artifacts:
    - path: "server/app/middleware/auth_middleware.py"
      issue: "Same fix as test 2"
  missing: []
  debug_session: ".planning/debug/auth-blocks-spa.md"
