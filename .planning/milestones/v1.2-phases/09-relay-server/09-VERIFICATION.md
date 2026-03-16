---
phase: 09-relay-server
verified: 2026-03-11T00:00:00Z
status: passed
score: 16/16 must-haves verified
re_verification: false
---

# Phase 9: Relay Server Verification Report

**Phase Goal:** A public-facing relay server accepts agent connections, routes browser HTTP requests through the tunnel to the correct agent, and handles mount lifecycle
**Verified:** 2026-03-11
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | MountRegistry register/deregister/get_connection lifecycle works correctly | VERIFIED | Full implementation in `relay/app/services/mount_registry.py`; 20 registry tests pass |
| 2  | get_connection raises MountNotFoundError for unknown codes, MountOfflineError for offline mounts, MountExpiredError for expired mounts | VERIFIED | Lines 73-80 of mount_registry.py; tests `test_get_connection_unknown_code_raises_not_found`, `test_get_connection_offline_mount_raises_offline_error`, `test_get_connection_expired_mount_raises_expired_error` all pass |
| 3  | Landing page renders at GET / with informational text and code input form | VERIFIED | `relay/app/routers/landing.py` GET / returns TemplateResponse("landing.html"); test_landing_page_returns_200 passes |
| 4  | GET /?code=XXXX redirects 302 to /m/XXXX/ | VERIFIED | `landing.py` line 23 returns RedirectResponse with status_code=302; test_code_redirect_returns_302 and test_code_redirect_location_header pass |
| 5  | Error templates render without errors and extend base.html | VERIFIED | All four templates use `{% extends "base.html" %}`; test_all_error_templates_extend_base passes |
| 6  | not_found template includes a code input field for retry | VERIFIED | `not_found.html` contains `<input type="text" name="code">`; test_not_found_template_contains_code_input and test_not_found_has_code_input pass |
| 7  | Agent connects via WebSocket, registers a mount code, and the relay runs heartbeat and receive loop until disconnect | VERIFIED | `agent_ws.py` lines 29-42: accept, TunnelConnection wrap, register, start_heartbeat, run_receive_loop |
| 8  | Browser GET /m/{code}/path returns proxied response body and status code from agent via StreamingResponse | VERIFIED | `mount_proxy.py` lines 110-123 return StreamingResponse; test_proxy_get passes with 200 + body "hello world" |
| 9  | Browser POST /m/{code}/path forwards request body in OPEN frame metadata to agent | VERIFIED | `mount_proxy.py` lines 70-85 read body and encode as latin-1 in metadata; test_proxy_post_body passes |
| 10 | When mount code is not found, proxy returns 404 with not_found.html including code retry input | VERIFIED | Lines 57-60 in mount_proxy.py; test_proxy_not_found (404) and test_not_found_has_code_input (input[name=code]) pass |
| 11 | When mount is offline, proxy returns 503 with offline.html | VERIFIED | Lines 61-64 in mount_proxy.py; test_proxy_offline passes with 503 + "offline" in body |
| 12 | When mount is expired, proxy returns 410 with expired.html | VERIFIED | Lines 65-68 in mount_proxy.py; test_proxy_expired_page passes with 410 + "expired" in body |
| 13 | When browser disconnects mid-stream, relay sends CANCEL frame to agent | VERIFIED | stream_generator in mount_proxy.py lines 110-116 calls send_cancel on is_disconnected |
| 14 | Agent WebSocket disconnect deregisters mount from registry | VERIFIED | agent_ws.py finally block lines 37-42: close + deregister with MountNotFoundError swallowed |
| 15 | Hop-by-hop headers stripped from forwarded request | VERIFIED | HOP_BY_HOP frozenset lines 20-31; test_proxy_strips_hop_by_hop_headers passes |
| 16 | 504 returned on first-byte timeout | VERIFIED | Lines 91-94 in mount_proxy.py catch FirstByteTimeoutError; test_proxy_first_byte_timeout passes |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `relay/app/services/mount_registry.py` | MountRegistry with register, deregister, get_connection, generate_mount_code | VERIFIED | 116 lines; full lifecycle implementation; exports MountRegistry, get_registry, set_registry, generate_mount_code |
| `relay/app/enums.py` | MountStatus enum | VERIFIED | MountStatus(str, Enum) with ONLINE, OFFLINE, EXPIRED values |
| `relay/app/exceptions.py` | Mount lifecycle exception hierarchy | VERIFIED | MountNotFoundError, MountOfflineError, MountExpiredError each storing .code attribute |
| `relay/app/routers/landing.py` | Landing page router | VERIFIED | GET / handler with code redirect or template render; exports `templates` |
| `relay/app/main.py` | Relay app factory | VERIFIED | create_relay_app() includes all three routers, CORS middleware, initialises registry; module-level `app` for uvicorn |
| `relay/app/routers/agent_ws.py` | Agent WebSocket endpoint | VERIFIED | /agent/ws WebSocket handler with full lifecycle |
| `relay/app/routers/mount_proxy.py` | HTTP proxy router with error page rendering | VERIFIED | /m/{code}/{path:path} for GET/POST/PUT/DELETE/PATCH with StreamingResponse and error pages |
| `relay/templates/base.html` | Shared Jinja2 layout | VERIFIED | System font stack, centered .card, light/dark prefers-color-scheme, {% block title %} and {% block content %} |
| `relay/templates/landing.html` | Landing page template | VERIFIED | Extends base.html; heading, info paragraph, form with name="code" input |
| `relay/templates/not_found.html` | Not found error page with code input | VERIFIED | Extends base.html; "Mount Not Found" heading; code retry input form |
| `relay/templates/offline.html` | Offline error page | VERIFIED | Extends base.html; "Mount Offline" heading; exact wording from CONTEXT |
| `relay/templates/expired.html` | Expired error page | VERIFIED | Extends base.html; "Mount Expired" heading |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `relay/app/routers/landing.py` | `relay/templates/landing.html` | Jinja2Templates.TemplateResponse | VERIFIED | Line 24: `templates.TemplateResponse(request, "landing.html")` |
| `relay/app/services/mount_registry.py` | `relay/app/exceptions.py` | raises typed exceptions | VERIFIED | Lines 62, 74, 77, 80, 89: `raise MountNotFoundError`, `raise MountOfflineError`, `raise MountExpiredError` |
| `relay/app/main.py` | `relay/app/routers/landing.py` | app.include_router | VERIFIED | Line 32: `application.include_router(landing_router)` |
| `relay/app/routers/agent_ws.py` | `relay/app/services/mount_registry.py` | registry.register and registry.deregister | VERIFIED | Lines 31, 40: `get_registry().register(code, conn)`, `get_registry().deregister(code)` |
| `relay/app/routers/mount_proxy.py` | `relay/app/services/mount_registry.py` | registry.get_connection | VERIFIED | Line 56: `get_registry().get_connection(code)` |
| `relay/app/routers/mount_proxy.py` | `tunnel/connection.py` | TunnelConnection.open_stream, send_open, read_stream, send_cancel | VERIFIED | Lines 88-114: `conn.open_stream`, `conn.send_open`, `conn.read_stream`, `conn.send_cancel` |
| `relay/app/main.py` | `relay/app/routers/agent_ws.py` | app.include_router | VERIFIED | Line 33: `application.include_router(agent_ws_router)` |
| `relay/app/main.py` | `relay/app/routers/mount_proxy.py` | app.include_router | VERIFIED | Line 34: `application.include_router(mount_proxy_router)` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| RELY-01 | 09-01, 09-02 | Relay server maintains in-memory mount registry mapping codes to agent WebSocket connections | SATISFIED | MountRegistry fully implemented; agent_ws.py registers/deregisters on connect/disconnect |
| RELY-02 | 09-02 | Browser HTTP requests to `/m/{code}/*` are proxied through the tunnel to the correct agent | SATISFIED | mount_proxy.py implements full StreamingResponse proxy over TunnelConnection |
| RELY-03 | 09-01 | Mount landing page allows users to enter a code or scan QR to access a mount | SATISFIED | GET / with informational text and code input form; redirects to /m/{code}/ on submit |
| RELY-04 | 09-01, 09-02 | Clean error pages display when a mount is offline, expired, or not found | SATISFIED | Three Jinja2 templates (not_found, offline, expired) rendered with correct HTTP status codes (404, 503, 410) |

All four requirements mapped to Phase 9 in REQUIREMENTS.md are satisfied. No orphaned requirements detected.

### Anti-Patterns Found

None. No TODO/FIXME/PLACEHOLDER comments, no empty implementations, no stub return values found in any phase 9 relay source files.

### Human Verification Required

None required. All observable behaviors are verifiable programmatically and all 42 tests pass.

### Gaps Summary

No gaps. All 16 observable truths verified, all 12 artifacts substantive and wired, all 8 key links confirmed, all 4 requirement IDs satisfied.

---

_Verified: 2026-03-11_
_Verifier: Claude (gsd-verifier)_
