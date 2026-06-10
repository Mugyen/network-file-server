# Project Log

## 2026-06-08: Persistence overhaul to SQLite-backed server state

Moved clipboard snippets, file requests, upload ownership tracking, and share-link persistence into `server_state.db` under `.wfs_data/`. Share secrets are now persisted too, so links survive restarts and the server no longer depends on the old JSON sidecar pattern for collaboration state. The remaining atomic JSON utility stays in place for legacy-compatible helpers, but the primary collaborative state now lives in SQLite.

## 2026-04-03: Phase 16 gap closure: Wire file TTL notifications

Wired broadcast_fn into file TTL sweep (was None), bridged drop box WebSocket via ASGIWebSocketTransport (was closed immediately), added tunnel control handler for agent expired-files responses, and fixed stale config test assertion.

## 2026-04-03: Phase 15 complete: UX Polish and Drop Box

Landing page with hero section, OG meta tags, and GitHub link. Connection status overlays (Host Offline/Mount Expired) via REST polling. Always-on drop box mount via httpx.ASGITransport in-process forwarding with reserved code protection. Per-file upload TTL (1h/6h/1d/7d/Never) with SQLite tracking, background sweep, expiry badges, WebSocket toast, and agent expired files prompt.

## 2026-03-30: Phase 14 complete: Persistent mount registry (14-02)

Wired SqliteMountRegistry into relay lifespan, agent_ws reclaim logic, and TTL sweep retention cleanup. Agents now mark_offline on disconnect instead of deregistering, can reclaim OFFLINE mounts by code+IP match, and mount_registered message includes reclaimed/remaining_ttl fields. All relay tests migrated from sync MountRegistry to async SqliteMountRegistry with in-memory SQLite.

## 2026-03-30: SqliteMountRegistry with persistence and reclaim (14-01)

Added SqliteMountRegistry class (relay/app/services/sqlite_registry.py) as async SQLite-backed drop-in for MountRegistry. Persists mount metadata across relay restarts via aiosqlite. Includes startup cleanup, expire(), try_reclaim() with IP match, delete_expired_before() for retention, and RelayConfig.db_path extension.

## 2026-03-30: Fix large file uploads through relay (FrameTooLargeError)

Relay proxy stuffed entire HTTP request body into OPEN frame metadata, exceeding 64KB frame limit. Fixed by streaming request body as chunked DATA frames (using request.stream() for memory efficiency) with zero-length sentinel for end-of-body. Agent side reconstructs body from DATA frames before forwarding to ASGI app. 3 new agent tests for body reconstruction.

## 2026-03-18: TTL enforcement, mount cap, and mount reg rate limiting (13-02)

Added mount TTL enforcement with background sweep (ttl_sweep.py), per-IP mount cap (default 5), and mount registration rate limiting via `limits` library directly on WebSocket endpoint. TTL query param on /agent/ws capped to config max (24h). Sweep sends ttl_warning before expiry and marks mounts EXPIRED.

## 2026-03-18: Config module, MountRecord extensions, and proxy rate limiting (13-01)

Centralized relay config into YAML+env-var config module (relay/config.yaml, relay/app/config.py). Extended MountRecord with agent_ip, created_at, expires_at fields for abuse tracking. Added SlowAPI rate limiting on proxy requests with configurable rate, styled HTML 429 page for browsers, and JSON 429 for API clients.

## 2026-03-16: SecureCookieMiddleware and conditional CORS lockdown (12-02)

SecureCookieMiddleware stamps Secure flag on Set-Cookie behind HTTPS (X-Forwarded-Proto). CORS locked down in production (explicit origins with credentials) while dev retains wildcard. Missing RELAY_ALLOWED_ORIGINS in production raises ValueError.

## 2026-03-16: Dockerize relay with health endpoint and structured logging (12-01)

Multi-stage Dockerfile (Node + Python + slim runtime), `/health` endpoint with mount count, `CloudJsonFormatter` for Cloud Logging JSON output, `RelayEnv` enum for dev/production mode switching, `deploy_relay.sh` Cloud Run deploy script, and structured request/agent logging.

## 2026-03-16: Rename project from network-file-server to network-file-server

Renamed project, CLI commands (`network-file-server`, `network-relay`), display names, templates, shell scripts, tests, planning docs, and `network_file_server.py` → `network_file_server.py`.

## 2026-03-16: LAN IP resolution for mount QR codes

When relay URL is localhost/127.0.0.1, the QR code and mount URL now show the LAN IP so phones on the same network can scan and connect. Also changed `run_mount_server.sh` to use `--relay` flag (translates to `--server` internally).

## 2026-03-16: Convenience run scripts and race condition fix

Added `run_relay.sh` and `run_mount_server.sh` — auto-rebuild client when source is newer than dist. Fixed critical race condition in agent receive loop: DATA frames were silently dropped because `open_stream` was called inside the spawned task instead of before it.

## 2026-03-16: Snippet copy button and relay CLI entry point (11-05)

Added copy-to-clipboard button to each SnippetCard (navigator.clipboard.writeText with 1.5s Check icon feedback). Created `relay/cli.py` with `network-relay` console script — binds to 0.0.0.0:8001 by default, supports `--host` and `--port` flags.

## 2026-03-13: Fix hardcoded /api/ paths broken in remote mount mode

Multiple client files hardcoded `/api/` instead of using `getApiBase()` from `remoteMount.ts`. In relay mode (`/m/{code}/`), these requests hit the relay root (404) instead of `/m/{code}/api/...`. Fixed: usePreview.ts, PreviewModal.tsx, files.ts (download, zip), clipboard.ts (delete), shares.ts (revoke), fileRequests.ts (all operations).

## 2026-03-13: Fix TTL auto-expiry not firing

Three issues: (1) `WebSocketClientAdapter` had no `close()` method — `TunnelConnection.close()` silently swallowed the `AttributeError`. (2) `TunnelConnection.close()` closed streams but not the underlying WebSocket, so the receive loop blocked forever. (3) `websockets.ConnectionClosed` wasn't caught by the disconnect handler, so TTL-triggered closes were treated as unexpected errors and triggered reconnect. Also fixed `_print_ttl_countdown` sleeping 60s before first print — now prints immediately with 10s intervals for short TTLs.

## 2026-03-13: Forward headers in WS_OPEN frames for WebSocket proxy auth

Relay's `proxy_websocket` sent only `path` and `query` in WS_OPEN metadata — no headers. The agent's local ASGI app rejected WebSocket connections for password-protected mounts (no session cookie). Fixed by forwarding non-hop-by-hop headers in WS_OPEN metadata and passing them to `httpx_ws.aconnect_ws`. Also disabled keepalive pings on in-process WS to prevent "Task was destroyed" warnings.

## 2026-03-12: Fix WS 403 on relay proxy for offline/unknown mounts

Relay's `proxy_websocket` called `websocket.close(1011)` before `websocket.accept()` when mount was not found — Starlette translates this into HTTP 403, causing the SPA's "Reconnecting..." loop. Fixed by accepting the upgrade first, then closing.

## 2026-03-12: Fix relay receive loop crash on WebSocket disconnect + stream teardown race

Relay's `run_receive_loop` crashed with RuntimeError when Starlette sent a `{"type": "websocket.disconnect"}` message — the loop only checked for "bytes"/"text" keys and silently looped, hitting Starlette's "cannot receive after disconnect" guard. Added `else: break` for disconnect messages. Also made `_dispatch_frame` tolerant of `StreamNotFoundError` (normal during WS teardown race). Also fixed agent's `handle_ws_open_frame` not calling `conn.open_stream(ws_id)` — WS_DATA frames for the stream had no registered target.

## 2026-03-12: Fix agent WebSocket connection dropping every 1-2 minutes

Neither side responded to heartbeat pings with pongs — both agent and relay started independent heartbeat loops sending `{"type": "ping"}` but neither had a ping→pong responder, causing 3 consecutive missed pongs and teardown after ~60-90s. Fixed by adding ping responders in `run_receive_loop` and both agent receive loops, removing redundant agent-side heartbeat (relay initiates, agent responds), and removing leaked `asyncio.shield` in heartbeat loop.

## 2026-03-12: Fix relay proxy HTML asset path rewriting for remote mounts

Relay's mount proxy now rewrites absolute asset paths (`/assets/...`) in HTML responses to `/m/{code}/assets/...` so the SPA's JS/CSS load correctly through the relay. Added `rewrite_html_asset_paths()` using regex replacement of `src="/` and `href="/` attributes. Strips `content-length` header from rewritten HTML (body size changes). 7 unit tests + 2 integration tests added. 540 tests green.

## 2026-03-11: WebSocket tunneling for relay proxy — real-time features in remote mode (11-03)

Added WS_OPEN (0x08), WS_DATA (0x09), WS_CLOSE (0x0A) to FrameType enum; `send_ws_open/data/close` methods to TunnelConnection; `_dispatch_frame` updated to route WS_DATA to stream queues and WS_CLOSE to close streams. Added `proxy_websocket` endpoint on relay at `/m/{code}/{path:path}` that accepts WS upgrades, opens tunnel stream, and bridges browser messages bidirectionally. Added `handle_ws_open_frame` to agent proxy that connects local WS to ASGI app and bridges both directions. Promoted httpx-ws to production dependency. 531 tests green.

## 2026-03-11: Mount password protection, TTL auto-expiry, and per-mount cookie scoping (11-01)

Added `agent/duration.py` (`parse_duration` converts `30m`/`2h`/`1d`/`90s` to seconds), `agent/exceptions.py` (`AgentExpiredError` for TTL-triggered exit without reconnect). Extended `ServerConfig` with `mount_code` field; auth cookies scoped to `/m/{code}/` for remote mounts. Added `--password` and `--ttl` flags to mount subcommand; TTL timer in `connect_and_serve` closes connection after duration and raises `AgentExpiredError`; `run_agent_loop` catches it and exits cleanly. 514 tests green.

## 2026-03-11: Agent proxy, connection loop, and mount CLI subcommand (10-02)

Added `agent/proxy.py` (`handle_open_frame` dispatches OPEN frames to local ASGI app via httpx, streams DATA+CLOSE back, handles CANCEL), `agent/connection.py` (`run_agent_loop` with exponential backoff reconnect, `_agent_receive_loop` dispatching concurrent tasks), and `agent/cli.py` (`run_mount` entry point). Extended `server/app/cli.py` with `mount` subcommand routing; backward-compatible LAN mode unchanged. 20 new TDD tests, full suite green.

## 2026-03-11: Agent package foundation and relay mount code generation (10-01)

Modified relay `/agent/ws` endpoint to generate mount codes server-side (optional preferred code for reconnect) and send `mount_registered` control message. Created `agent/` package with `WebSocketClientAdapter` (satisfies `WebSocketProtocol`), `print_mounted`/display functions, and `compute_backoff`. Moved httpx to production dependencies. 47 new TDD tests, 132 total green.

## 2026-03-11: Relay agent WebSocket and mount proxy (09-02)

Added `/agent/ws` WebSocket endpoint wrapping `TunnelConnection` with heartbeat and registry lifecycle, and `/m/{code}/{path}` HTTP proxy streaming agent responses with hop-by-hop header stripping and error page rendering. 9 new TDD tests, 424 total green.

## 2026-03-11: Relay server foundation (09-01)

Added `relay/` package with `MountStatus` enum, typed mount exceptions, `MountRegistry` service (register/deregister/get_connection with lifecycle state enforcement), and FastAPI app factory. Added Jinja2 templates (base, landing, not_found, offline, expired) and landing router with code redirect. 33 TDD tests green.

## 2026-03-11: Tunnel protocol primitives (08-01)

Added `tunnel/` package with binary frame serialization (`serialize_frame`/`deserialize_frame`), `FrameType` enum, typed exception hierarchy, `WebSocketProtocol` interface, and `MockWebSocket` test fixture. 22 TDD tests green.

## 2026-03-11: Fix auth middleware, session persistence, and read-only clipboard (05-UAT)

Fixed AuthMiddleware to only gate `/api/*` paths instead of all paths. Added session cookie probe on page load so login persists across tabs/refreshes. Made scratchpad readable in read-only mode (write actions hidden, content viewable).

## 2026-03-10: Frontend device discovery UI (07-02)

Added DevicesPanel slide-out with device type icons, "You" badge, live connection duration, and real-time connect/disconnect updates. Wired Monitor header button with device count badge visible in all modes.

## 2026-03-10: Backend device discovery (07-01)

Extended WebSocket infrastructure with DeviceType enum, DeviceInfo dataclass, parse_device_type UA classifier, device_list message on connect with your_device_id, and enriched connect/disconnect toasts. 21 tests (12 new).

## 2026-03-10: Frontend share link UI (06-02)

Added ShareDialog for creating share links with TTL picker and clipboard copy, ShareLinksPanel slide-out for listing/revoking active links, Share button on file rows, and Share Links header button in App.

## 2026-03-10: Share link backend and templates (06-01)

Added ShareLinkService with create/validate/revoke/list and auto-expiry cleanup, ShareTTL enum (15m/1h/6h/24h), share router with 5 endpoints, 3 standalone Jinja2 HTML pages (download/expired/unavailable) with dark mode, and auth middleware bypass for /share routes. 36 new tests.

## 2026-03-10: Frontend access control UI (05-03)

Added LoginPage for password-protected servers, DropBoxPage for receive-only mode with drag-and-drop upload zone, ModeBadges (amber Read Only, blue Protected pills), mode-aware root routing in main.tsx, and read-only write-control hiding across App/FileList/FileRow/BatchToolbar. CLI banner prints active modes.

## 2026-03-10: Auth middleware, route guards, and mode restrictions (05-02)

Added pure ASGI auth middleware with cookie-based session gating, login/logout endpoints, read-only write guards on all 10 write surfaces, and receive-mode API restrictions. Extended server-info with mode fields. 37 new integration tests.

## 2026-03-10: CLI flags, config, and auth service for access control (05-01)

Added --password, --read-only, --receive CLI flags with mutual exclusion validation. Extended ServerConfig with access control fields. Created AuthTokenService with bcrypt password hashing and itsdangerous signed session tokens.

## 2026-03-09: File request system with real-time sync (04-03)

Added file request feature: devices can request specific files, others fulfill via upload button or drag-and-drop. Banners above file list show pending/fulfilled status with WS real-time sync. Only requester can dismiss. JSON persistence survives server restart. 15 backend tests.

## 2026-03-09: Shared clipboard scratchpad (04-02)

Added real-time shared clipboard with slide-out scratchpad panel. Named snippets with CRUD, 300ms debounced WS sync for content edits, JSON persistence on server. Max 50 snippets, 10000 chars each.

## 2026-03-09: FastAPI backend foundation (01-01)

Scaffolded FastAPI backend with config validation, path traversal guard (resolve_safe_path), file listing API (GET /api/files), CORS middleware, and CLI entry point (network-file-server command). 43 tests covering all modules.

## 2026-03-09: QR code and discovery services (01-02)

Added QR code generation (ASCII terminal + SVG web), LAN IP auto-detection, and GET /api/server-info endpoint. ASCII QR code prints on server startup for instant device connection.

## 2026-03-09: File management API endpoints (02-01)

Added 6 API endpoints: upload (multipart with conflict resolution), download (single file + batch ZIP via zipstream-ng), rename, delete, batch delete, and create folder. All endpoints validate paths through resolve_safe_path. 146 tests.

## 2026-03-09: Folder navigation, breadcrumbs, and file icons (02-02)

Added folder navigation via double-click with URL-synced breadcrumbs (?path= param), browser back/forward support, lucide-react file type icons (40+ extensions mapped), and responsive table layout hiding Size/Modified columns on mobile.

## 2026-03-09: Upload UI with drag-and-drop and progress tracking (02-03)

Added drag-and-drop upload overlay, XHR-based file upload with per-file progress bars in a floating panel, toolbar with Upload button, and per-file conflict resolution dialog (overwrite/rename/skip). Concurrency limited to 3 simultaneous uploads.

## 2026-03-09: Complete file management UI wiring (02-04)

Wired all file management features into the UI: checkbox selection with batch operations (ZIP download, batch delete with confirmation modal), inline rename, create folder dialog, individual file download, drag-and-drop upload integration. Gmail-style batch toolbar swaps in when items are selected.

## 2026-03-09: Search and preview API with file category system (03-01)

Added recursive file search endpoint (GET /api/files/search), inline file preview endpoint (GET /api/files/preview) with Range request support for video/audio seeking, and TypeScript file category type system mapping 90+ extensions to 10 categories. 18 new integration tests, 166 total.

## 2026-03-09: Fix upload failures

Fixed three upload bugs: (1) replaced crypto.randomUUID() with counter-based ID — randomUUID is unavailable on HTTP LAN IPs (non-secure context), silently breaking all uploads; (2) added processingIds ref guard to prevent React StrictMode from double-firing uploads; (3) resolved client/dist path relative to project root instead of CWD so SPA serves correctly regardless of launch directory.

## 2026-03-09: Search, filter, sort, and dark mode UI (03-02)

Added SearchBar with debounced backend search and instant client-side filtering, FilterChips for multi-select category filtering (10 types), sortable column headers (directories-first), and dark mode with system preference detection, manual toggle, and localStorage persistence. FOUC prevented via inline head script.

## 2026-03-09: Unified file preview modal (03-03)

Added PreviewModal with 7 sub-components: image gallery (zoom toggle, arrow navigation), video/audio players (native HTML5 with Range seeking), PDF iframe viewer, syntax-highlighted code (PrismLight with 23 languages), GFM markdown renderer, and file info fallback. Modal has close/escape/backdrop, open-in-new-tab, and download controls.

## 2026-03-09: WebSocket infrastructure with toast notifications and connection status (04-01)

Added WebSocket endpoint (/ws) with ConnectionManager for device tracking and broadcast, atomic JSON persistence utility, toast notifications (file upload, device connect/disconnect) with auto-dismiss and overflow collapse, connection status dot with device count tooltip, and reconnecting banner with exponential backoff. 15 backend tests.

## 2026-05-14: PWA Web Share Target for Android upload bypass

Added manifest.webmanifest with share_target POST/multipart, minimal sw.js for installability, and POST /api/share-upload route that accepts shared files and 303-redirects to ../. Lets users on devices with broken file pickers (Realme/OPPO, some Samsung) upload via Android's share sheet instead. Also added accept="*/*" and 0.0.0.0 LAN-IP rewriting fixes.

## 2026-05-18: Accounts library — users, nested groups, credentials, quotas (v1.3 phase 1)

Added framework-agnostic `accounts/` package (enums, models, exceptions, bcrypt passwords, AccountStore ABC, SqliteAccountStore, transitive group resolution with write- and read-time cycle detection, per-user quota). Registered in pyproject wheel packages. 39 tests (happy/edge/failure + fastapi-free import isolation); ruff clean.

## 2026-05-18: Relay accounts config + session signer + store wiring (v1.3 phase 2)

Added session_secret/admin_users/accounts_db_path/default_user_quota_bytes to RelayConfig (env overrides; ephemeral secret + warning if unset). New relay/app/services/session.py (RelaySession: signed session + short-lived agent-owner tokens, salted) and account_store.py singleton. Wired SqliteAccountStore + RelaySession into relay lifespan. Added InvalidSessionError/AuthenticationRequiredError/AccessDeniedError. 28 new tests; full relay+accounts suite 264 green.

## 2026-05-18: Relay auth + admin HTTP API (v1.3 phase 3)

Added relay/app/dependencies.py (get_optional_identity / get_current_identity / require_admin, admins from config), routers/auth.py (POST /auth/signup|login|logout|agent-token, GET /auth/me with httponly wfs_session cookie) and routers/admin.py (admin-gated user enable/disable, group CRUD, membership add-by-name/remove with cycle+dup mapping to 409). Wired into relay app. 21 new tests; full relay+accounts suite 285 green.

## 2026-05-18: Agent-as-owner handshake + mount policy persistence (v1.3 phase 4 + phase 5 data layer)

Added agent/auth.py (AgentOwner, parse_allow_entry, fetch_agent_token), agent CLI flags --login/--password-stdin/--access-mode/--allow (password kept), and an agent_auth control frame sent before mount_registered. Relay agent_ws now reads/validates the handshake, verifies the owner token, resolves allowlist names→ids, and persists policy. SqliteMountRegistry gained owner_user_id/access_mode/has_password columns (migrated), a mount_policy table, set_owner_policy/get_policy, and try_reclaim_as_owner (IP-independent owner reclaim). MountPolicy/PolicyEntry models added. Agent stops (no retry) on AgentAuthError. 17 new tests; full suite 800 green.

## 2026-05-18: Relay access enforcement at the proxy (v1.3 phase 5)

Added relay/app/services/access_policy.py (authorize + identity_from_cookies) implementing the access-decision model: allowlisted signed-in users pass identified (password bypassed downstream), OPEN mounts allow anon, RESTRICTED+password falls through to the server password gate, RESTRICTED+no-password denies (AuthenticationRequiredError→302/401, AccessDeniedError→403 forbidden.html). Wired enforcement into mount_proxy proxy_request and proxy_websocket (close 1008). Legacy/dropbox mounts fail open. 12 new tests; full suite 812 green.

## 2026-05-18: Trusted relay identity propagation + per-request server role (v1.3 phase 6 core)

Relay mount_proxy now strips inbound X-WFS-* and injects authoritative X-WFS-User/Role/Auth-Bypass for allowlisted users (HTTP + WS). New server/app/services/relay_identity.py gates trust on relay-served mode (mount_code set) so LAN clients cannot spoof. auth_middleware honors X-WFS-Auth-Bypass (relay-served only); mode_guard derives per-request role from X-WFS-Role with global read_only/receive fallback; server-info exposes current_user/current_role/access_mode. 19 new tests incl. LAN spoof regressions; full suite 821 green. NOTE: RECEIVE currently = upload-only (existing receive semantics); the "see own uploads" refinement is still outstanding.

## 2026-05-19: RECEIVE role = upload + see own uploads (v1.3 phase 6 completion)

Added server/app/services/upload_index.py (JSON sidecar mapping rel_path->uploader, reuses persistence util). mode_guard: require_write_access now allows RECEIVE (upload), require_full_access still blocks RECEIVE (destructive ops), new require_browse_access + receive_scope_user. files.py records uploader on upload and scopes list/download/preview to the RECEIVE user's own files (search returns empty for RECEIVE; sidecar hidden). 8 new tests; full suite 830 green.

## 2026-05-19: Per-user relay storage + quota (v1.3 phase 7)

Added relay/app/services/user_storage.py (isolated <data_dir>/users/<id> dir, usage walk, quota = accounts override else relay default) and routers/user_storage.py (/me/quota, /me/files list/upload/download/delete; login-required; 413 on quota exceeded with content-length pre-check + post-write rollback). Reuses server file_service helpers (path-traversal safe). Removed a long-stale unused import in relay/app/main.py. 6 tests; full suite 836 green.

## 2026-05-19: Client SPA — relay login/signup/admin/403 + access requests (v1.3 phase 8 frontend)

Added client/src/api/accounts.ts (relay-root auth/admin/requests client) and client/src/pages/{LoginPage,SignupPage,AdminDashboard,Forbidden403}.tsx. main.tsx routes /login,/signup,/admin,/403 to relay pages and redirects mount access to /login?next= on relay 302/401. Client builds clean (tsc + vite). Browser/Playwright verification is the user's step (no headless browser here).

## 2026-05-19: Rate limiting, scripts, docs, security pass (v1.3 phase 9)

Added config-driven per-IP rate limits (RELAY_AUTH_SIGNUP_RATE 5/hour, AUTH_LOGIN_RATE 10/min, AUTH_AGENT_TOKEN_RATE 10/min) on /auth/signup|login|agent-token via the shared slowapi limiter (response param added for header injection). Created scripts/{install_setup,build,run,test,clean}.sh (CLAUDE rule 12). README documents the accounts model/env/flows; feature-ideas/48 marked largely-delivered (API keys + SSO still open). Security pass: bcrypt constant-time, generic 401s, httponly+samesite+secure-via-proxy session cookie, 120s agent-token max-age, inbound x-wfs-* strip regression covered. 3 new tests; full suite 848 green; all feature files ruff-clean.

## 2026-05-19: Client WS reconnect backoff gate

useWebSocket now resets the backoff attempt counter only after a connection stays open STABLE_CONNECTION_MS (3s), not immediately in onopen. The relay accepts the WS upgrade before it knows the agent is reachable, so a dead mount produced a brief onopen→onclose that reset the counter every attempt, hammering the relay every ~1s. Failed/short connections now escalate to the 30s cap. Client tsc clean.

## 2026-05-19: Tunnel backpressure + stale-connection guard

TunnelConnection._dispatch_frame is now async and awaits queue.put instead of put_nowait, so a slow consumer (e.g. browser pulling a media preview) applies TCP backpressure to the sender instead of raising QueueFull and tearing down the whole agent tunnel; relay and both agent receive loops updated to await it. Added TunnelConnection.is_closed; both registries' get_connection now raise MountOfflineError for a registered-but-closed connection so post-disconnect requests get a clean offline response instead of RuntimeError on a closed WebSocket. Added backpressure + closed-guard tests (mocks gained is_closed); full suite 851 green.

## 2026-05-19: Playwright auth e2e

Added @playwright/test + client/playwright.config.ts + client/e2e/auth.spec.ts and scripts/e2e.sh, which boots a throwaway relay (temp DBs, RELAY_ADMIN_USERS=admin), seeds admin/alice/bob, brings up an open and an alice-owned restricted mount, then runs 5 specs: signup, login (+wrong password), open-mount guest access, restricted anonymous→/login?next= redirect, and restricted denial→/403 request→admin approval→access granted. Wired install_setup.sh (playwright install chromium), clean.sh, client/.gitignore, README. 5/5 green. Note: server-rendered forbidden.html does not link to the React /403 request-access UI — reachable only by direct navigation (UX gap, not a test failure).

## 2026-06-09: Fable 5 codebase review

Added docs/fable-5-codebase-review.md — full-codebase review (functionality/reusability map, strengths, weaknesses with file:line evidence) by Claude Fable 5. Top findings: ttl_warned never persisted (warnings re-fire), text-only WS bridge, close() missing from WebSocketProtocol, swallowed exceptions in tunnel glue, server⇄relay import cycle, blocking I/O in async handlers, no CI.

## 2026-06-09: Fable 5 remediation plan

Added docs/fable-5-remediation-plan.md — design doc addressing all 22 weaknesses from the Fable 5 review: per-item problem/why/solution/why entries (no code), an 8-phase plan of action (safety net → bugs → observability → concurrency → decoupling → DI → frontend → test rebalancing), dependency/risk register, per-phase verification, and an A1–G5 traceability table.

## 2026-06-10: Remediation phase 1 — safety net

Added .github/workflows/ci.yml (ruff + mypy + pytest backend job, tsc + vitest client job, manual-dispatch e2e job), [tool.ruff] + strict [tool.mypy] for tunnel/accounts/shared in pyproject, fixed all 94 ruff findings + 19 mypy findings (incl. adding close() to WebSocketProtocol), deleted dead root files (network_file_server.py, start_server.sh, main.py, requirements.txt, run.sh, run_relay.sh, run_mount_server.sh), extended scripts/test.sh with lint/typecheck/vitest, excluded e2e/ from vitest. Suite: 852 pytest + 11 vitest green.

## 2026-06-10: Remediation phase 2 — correctness bugs A1–A4

A1: ttl_warned now persisted via SqliteMountRegistry.mark_ttl_warned (re-registration resets it). A2: WS bridge carries binary+text via new tunnel/ws_payload codec (1-byte kind marker), applied to agent proxy, relay mount proxy, and dropbox bridge. A3: WebSocketProtocol gained close(); dead get_event_loop removed (done in phase 1's mypy pass). A4: stable UUID device identity (getDeviceId) separate from cosmetic display name — file-request ownership and /ws connection keying use it; multi-tab eviction guard added. Suite: 869 pytest + 17 vitest green.

## 2026-06-10: Remediation phase 3 — observability

Eliminated all silent exception swallows in tunnel glue: agent/proxy.py + mount_proxy.py WS bridges now log task errors (debug for expected disconnect races, exception for unexpected), agent_ws handshake failures log warnings with client IP, server create_app config swallows log warnings, websocket snippet_update rejections log warnings, mark_offline/FileTtlDb no-ops log debug, tunnel close teardown logs debug. Client: useClipboard mutations surface failures via new ERROR toast type (with optimistic-update rollback), background loads + search fallback log console.error. Suite: 870 pytest + 17 vitest green.

## 2026-06-10: Remediation phase 4 — concurrency & performance

D1: get_files list_directory + relay user_storage (list/delete/quota-walk/rollback) offloaded via asyncio.to_thread (sync `def` routes already threadpooled — annotated search route to prevent regressions). D2: WAL journal mode for relay registry + accounts store (matching server store); FileTtlDb gained create()/close() with its own WAL connection instead of sharing the registry's. G4: AccountStore.get_users_by_ids batch lookup kills access-request N+1. G5: ShareLinkService._active_links now lock-guarded (RLock, matching ServerStateStore). New tests: batch lookup (6), WAL/own-connection (3), event-loop-liveness smoke. Suite: 880 pytest + 17 vitest green.

## 2026-06-10: Remediation phase 5 — decoupling

C1: qr_service/network_service moved to shared/{qr,network}.py (agent/display.py no longer imports server). C2: agent gained MountAppContext + AppFactory — connect_and_serve/run_agent_loop/run_mount take an injected ASGI app factory; server/app/cli.py build_mount_app is the composition root (agent has zero server imports). C3: server owns FileTtlProvider protocol (server/app/services/file_ttl_provider.py); relay injects FileTtlDb at lifespan — server→relay import deleted, cycle broken. C4: server/__init__.py declares the public interface (create_app lazy via PEP 562); relay imports only `from server import ...`. New tests/test_import_boundaries.py enforces all directions via AST scan. Suite: 886 pytest + 17 vitest green.

## 2026-06-10: tests/ migrated to per-app DI

tests/{relay/test_dropbox.py,relay/test_phase4_concurrency.py,agent/test_agent_connection_task2.py} migrated off removed globals (set_server_config/get_server_config/set_file_ttl_provider) to create_app(config) + app.state injection (dropbox TTL provider via get_dropbox_app().state.file_ttl_provider). 522/523 green; 1 failure is a pre-existing production bug in server/app/routers/server_info.py (stale trusted_role/trusted_user call signature).

## 2026-06-10: server/tests migrated to per-app DI

server/tests/* (13 files incl. conftest) migrated off removed singletons (set_server_config/set_token_service/set_share_service/module-level manager/lazy service getters) to create_app(config) + app.state; share expiry tests now use the ShareLinkService now_fn clock seam instead of mutating _active_links. 352/364 green; the 12 failures are all the known production bug in server/app/routers/server_info.py (stale one-arg trusted_role/trusted_user calls).

## 2026-06-10: Remediation phase 6 — dependency injection

Retired the server's module-level singletons: create_app(config) now required-arg; config, token/share/clipboard/file-request services + ConnectionManager + file_ttl_provider all live on app.state; routers consume via server/app/dependencies.py Depends accessors; relay_identity/mode_guard/AuthMiddleware take config explicitly; removed import-time `app = create_app()` (CLI passes the app object to uvicorn); dropbox + agent factory build apps without touching globals; ShareLinkService.create_link returns the full record + now_fn clock seam (tests no longer poke _active_links). Sqlite store keyed-cache and relay lifespan singletons retained by design (single relay per process). New server/tests/test_multi_instance.py pins two-apps-one-process isolation + DI override seam. Suite: 891 pytest + 17 vitest + e2e 5/5 green.

## 2026-06-10: Client hardening — WS guards, error boundaries, useAdmin

Added src/utils/wsGuards.ts (hand-rolled runtime guards for all consumed WS payloads, applied in useWebSocket/useClipboard/useFileRequests with log-and-skip on malformed data), src/components/ErrorBoundary.tsx wrapping every pickRoot() target in main.tsx, and src/hooks/useAdmin.ts extracting AdminDashboard data/mutations/guarded-error state (refresh failures now surface as the notice). 60 new vitest tests; suite 77/77 green.

## 2026-06-10: Client refactor — App.tsx god component split into contexts

Split App.tsx (603 -> 216 lines) along hook boundaries into src/contexts/ NotificationsProvider (useToast + owns ToastContainer), BrowseProvider (listing/path/search/sort/filter/selection/preview + file-op handlers), and UploadProvider (useUpload + drag-drop, nested in Browse); dialog state moved down into new FileBrowserSection/HeaderActions/UploadWidgets components, and the WS toast handler now uses the isToastPayload runtime guard. 12 new vitest tests (consumer hooks throw outside providers + slice behavior); suite 89 vitest + 9 Playwright green, behavior unchanged.

## 2026-06-10: Client lint clean — eslint gate re-enabled

Fixed all 12 remaining eslint findings (react-hooks compiler rules: hoisted render-created icon components, converted setState-in-effect to adjust-state-during-render/derived-initial-state/promise continuations, connectRef for WS reconnect, fileTtl dep, ref-snapshot cleanup, removed unused Toolbar prop, entry-module react-refresh override) and re-enabled `npm run lint` in CI and scripts/test.sh. Gates green: lint 0 findings, tsc, 89 vitest, 9 Playwright.

## 2026-06-10: Remediation phase 7 — frontend structure & trust boundaries

F4: apiDeleteNoBody added; shares/clipboard raw-fetch workarounds removed. F5: cycleThemeMode deduped into useTheme; UploadTTL const object (Toolbar + useUpload typed); serverMode\! replaced with explicit narrowing; useAdmin hook extracted from AdminDashboard. F2: hand-rolled WS type guards (utils/wsGuards.ts, 47 tests) applied in useWebSocket/useClipboard/useFileRequests + App toast handler. F3: ErrorBoundary per pickRoot target. F1: App.tsx 603→216 lines via NotificationsProvider/BrowseProvider/UploadProvider + FileBrowserSection/HeaderActions/UploadWidgets; dialog state moved down. All 12 eslint findings fixed (incl. latent stale-TTL upload bug); lint re-enabled in CI + scripts/test.sh. New e2e/core-flows.spec.ts (browse/upload/preview/folders through real tunnel). Client: 89 vitest + 9 Playwright green.

## 2026-06-10: Remediation phase 8 — test-coverage rebalancing

Added tests/integration/test_full_path.py — real relay (uvicorn) + real agent over a real WebSocket via build_mount_app, exercising browse/upload/download/WS-bridging end to end (module-scoped stack; teardown bounds + straggler sweep). Added tests/tunnel/test_stream_iter.py — read_stream_iter drain-after-close/cancellation/interleaving + randomized framing round-trips and corruption rejection (8 tests). Production fix surfaced by the integration work: agent receive loops now cancel in-flight handler tasks when shut down by cancellation (previously could hang agent shutdown). Client units (89) and core-flow Playwright specs were delivered in phase 7. Final: 902 pytest + 89 vitest + 9 Playwright, ruff/mypy/eslint/tsc clean.

## 2026-06-10: CI fixes — npm peer-dep conflict + SPA 404s without client build

Aligned @vitest/coverage-v8 to ^3.2.4 (matching vitest 3.x; 4.0.18 broke `npm ci` with ERESOLVE). Extracted relay's SPA placeholder shell into shared/spa.py and made the server's SPA catch-all always register — serving the placeholder when client/dist is absent (CI backend job), fixing test_unauthenticated_spa_serves_html and test_dropbox_serves_file_browser 404s. +7 tests (909 pytest).

## 2026-06-10: CI — bump deprecated Node 20 actions

checkout v4→v6, setup-node v4→v6, setup-uv v5→v8 (Node 24-native; GitHub forces Node 24 runtimes from 2026-06-16). Job-level node-version: 20 unchanged.

## 2026-06-10: Architecture remediation plan

Added docs/architecture-remediation-plan.md — 11-phase plan from the architecture review (exception handling, singleton removal, async sqlite, tunnel hardening, dropbox unification, signed identity, client codegen/state layer/tests).

## 2026-06-10: Remediation phase 1 — centralized exception handling

New server/relay error_handlers.py map all domain exceptions to HTTP centrally; routers no longer construct error responses (files/clipboard/share/share_target/access_requests). New domain exceptions: InvalidFileRequestError, SnippetNotFoundError, SnippetValidationError (replacing raw ValueError/KeyError). Error shape standardized to {"detail": ...}. +21 tests (930 pytest).

## 2026-06-10: Relay test migration to per-app RelayState

Migrated 6 relay test files off the deleted module-level singletons (get/set_config, get/set_registry, get/set_relay_session, get/set_account_store, reset_mount_reg_limiter) to app.state.relay wiring; deleted 6 singleton-mechanics tests. 63 tests pass.

Migrated test_dropbox.py, test_dropbox_ws.py, test_agent_expired_files.py, and integration test_full_path.py to app.state.relay wiring (init_dropbox tuple return, RelayState file_ttl_db/dropbox fields, 3-arg _handle_agent_control_for_mount). 18 tests pass.

## 2026-06-10: Remediation phase 2 — module-level singletons eliminated

Server (2a): removed get_state_store() process cache; one ServerStateStore per app via DI. Relay (2b): RelayState dataclass on app.state.relay replaces 7 module globals (config/registry/session/account_store/file_ttl_db/dropbox×2) + per-app mount-reg rate limiter; account_store.py deleted; module-level app removed (uvicorn factory=True); slowapi limiter+rates remain the single documented process-global (3rd-party constraint). authorize()/identity_from_cookies()/user_storage take explicit deps. 925 pytest green.

## 2026-06-10: Remediation phase 3 — event loop never blocks on SQLite

Service layer (clipboard/share/file-request/upload_index) now offloads all ServerStateStore calls via asyncio.to_thread; ShareLinkService methods went async (router + tests updated). Deviation from plan documented: store stays sync sqlite3 (create_app is a sync factory; lifespan-less test architecture), threading contract documented in sqlite_store.py. New shared/sqlite_kernel.py (is_new_db/open_wal_db/run_schema) adopted by relay sqlite_registry + file_ttl_db; accounts keeps its own bootstrap (leaf-package import boundary). 933 pytest green (+8 kernel tests).

## 2026-06-10: Remediation phase 4 — tunnel protocol hardening

PROTOCOL_VERSION=1 exchanged in agent_auth; relay rejects skewed/missing versions at handshake (close 1008). New tunnel/metadata.py: RequestMetadata/WsOpenMetadata wire contract with 16KiB cap + typed MetadataError validation on both ends (malformed OPEN now answers 400 instead of crashing the agent loop). Agent runs its own 30s heartbeat (detects half-dead relay sockets). Relay send paths wrap transport failures as TunnelSendError -> 503/431 instead of unhandled 500. 949 pytest green (+16 tests).

## 2026-06-10: Remediation phase 5 — HTML rewriter extraction + hardening

New relay/app/services/html_rewriter.py: charset-aware decode (Content-Type param, default utf-8), undecodable/unknown-charset bodies pass through unmodified, 5MiB rewrite cap — oversized HTML streams through unrewritten (buffered prefix + remainder) instead of being buffered unbounded. mount_proxy uses it on both tunnel and dropbox paths; the proxy can no longer crash on non-UTF-8 HTML. Rewriter unit tests moved out of test_mount_proxy + 8 hardening tests. 957 pytest green.

## 2026-06-10: Remediation phase 6 — dropbox is a first-class local mount

New relay/app/services/local_mount.py: LocalAsgiMount (app + forwarding client + WS bridge + aclose). RelayState.local_mounts dict replaces dropbox_app/dropbox_client fields; lifespan registers/closes the drop box through it. mount_proxy now has ZERO dropbox references — both HTTP and WS paths dispatch on local_mounts membership; the ~70-line bespoke WS bridge moved into the service. init_dropbox returns the mount. 959 pytest green (+2 tests).

## 2026-06-10: Remediation phase 7 — signed identity headers + AccessMode.LEGACY

New shared/identity_sig.py (HMAC-SHA256 over user|role|bypass). Agent mints a per-mount secret each connect, passes it to its embedded server (ServerConfig.identity_secret) and the relay (agent_auth); relay signs injected X-WFS-* headers (mount_proxy), server verifies before trusting (relay_identity). Closed a LATENT hole: AuthMiddleware did its own raw bypass check — now routes through signature-verifying is_auth_bypassed. Local-mount forward strips client X-WFS-*. AccessMode.LEGACY added; pre-v1.3 access_mode ALTER default → 'legacy'; access_policy logs the fail-open explicitly. 974 pytest green (+17 trust-boundary/sig tests incl. forged/cross-secret/unsigned rejection).

## 2026-06-10: Remediation phase 8 — composition cleanups

(a) server/app/bootstrap.py is the new composition root (build_mount_app, run_mount_agent, run_lan_server); cli.py is now parsing + delegation only and no longer imports the agent; import-boundaries whitelist points at bootstrap. (b) TunnelConnection.run_receive_loop_with_handlers(on_open, on_ws_open) added (shared private core); the agent's two hand-rolled receive loops deleted in favour of _OpenFrameHandlers (task spawn/drain) + a registered expired_files control handler — the agent no longer pokes conn._ws/_dispatch_frame. (c) mount_proxy left at 520 lines (cohesive; high-value extractions already done in 5-6). 974 pytest green.

## 2026-06-10: Remediation phase 9 — client API types generated from OpenAPI

New server/app/openapi_dump.py + scripts/gen_api_types.sh dump the server OpenAPI schema and run openapi-typescript into client/src/types/api.gen.ts. Added response_model to the files routes (DirectoryListing/SearchResult/UploadResult) and expires_at to FileEntry so the schema is the true contract. Client types/{files,serverInfo,clipboard,fileRequests}.ts now derive from the generated schema (runtime consts FileType/RequestStatus kept). New CI api-types job regenerates + git diff --exit-code (drift fails the build). 974 pytest + 89 vitest green; tsc/eslint clean.
