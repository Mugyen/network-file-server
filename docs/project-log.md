# Project Log

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

Scaffolded FastAPI backend with config validation, path traversal guard (resolve_safe_path), file listing API (GET /api/files), CORS middleware, and CLI entry point (wifi-file-server command). 43 tests covering all modules.

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
