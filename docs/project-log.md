# Project Log

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
