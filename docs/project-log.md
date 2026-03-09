# Project Log

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
