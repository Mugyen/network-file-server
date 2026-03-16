# Milestones

## v1.2 Remote Mounts (Shipped: 2026-03-16)

**Phases completed:** 4 phases, 11 plans
**Codebase:** ~19,500 LOC (13,098 Python + 6,400 TypeScript)
**Timeline:** 5 days (2026-03-12 → 2026-03-16)

**Delivered:** Internet file sharing via relay tunnel — mount a local folder through a public relay server, accessible to anyone with the mount code or QR scan, with all v1.0/v1.1 features working identically through the tunnel.

**Key accomplishments:**
- Binary WebSocket tunnel protocol with 21-byte frame headers, UUID-correlated multiplexing, and per-stream backpressure
- Relay server routing browser requests at `/m/{code}/*` through tunnel to agents, with mount registry and error pages
- `wifi-file-server mount` CLI with auto-reconnect, QR code display, and LAN IP resolution for phone access
- Password protection (`--password`) and auto-expiry (`--ttl`) for remote mounts
- SPA dynamic relay prefix detection so all v1.0/v1.1 features work identically through remote mounts
- WebSocket tunneling for real-time clipboard sync, transfer notifications, and device discovery through relay
- Chunked DATA frame streaming for large file uploads through the relay proxy

---

## v1.1 Share & Access Control (Shipped: 2026-03-11)

**Phases completed:** 3 phases, 7 plans
**Lines added:** +7,291
**Codebase:** ~13,150 LOC (6,966 Python + 6,184 TypeScript)
**Files modified:** 81
**Timeline:** 3 days (2026-03-09 → 2026-03-11)
**Git range:** `test(05-01)` → `feat(05)`

**Delivered:** Access control modes (password, read-only, receive), expiring share links with clean download pages, and real-time device discovery — completing the sharing and security layer.

**Key accomplishments:**
- Password protection with bcrypt hashing, session cookies, login page, and logout
- Read-only mode with backend enforcement on 10 write surfaces and frontend control hiding
- Receive mode / digital drop box with upload-only drag-and-drop interface
- Expiring share links with TTL selection (15min–24hr), Jinja2 download/expired pages, and operator revocation
- Real-time device discovery panel with device-type icons (phone/laptop/tablet) and "You" badge
- Share links bypass password protection — the token is the authentication

---

## v1.0 MVP (Shipped: 2026-03-09)

**Phases completed:** 4 phases, 13 plans, ~29 tasks
**Lines of code:** ~9,600 (4,700 Python + 4,900 TypeScript)
**Files modified:** 141
**Timeline:** 1 day (2026-03-09)
**Git range:** `feat(01-01)` → `feat(04-03)`

**Delivered:** A polished LAN file sharing tool with React + FastAPI — scan QR, drop files, preview media, share clipboard, request files, all in real-time.

**Key accomplishments:**
- FastAPI backend with path traversal protection serving React SPA with Tailwind CSS v4
- QR code discovery (ASCII terminal + SVG web) for instant device connection
- Full file management: drag-and-drop upload with progress, ZIP download, batch ops, folders, rename
- Search, filter by type category, sort — instant client-side + recursive backend search
- Media preview: image lightbox, video/audio player, PDF viewer, syntax-highlighted code, rendered markdown
- Real-time WebSocket features: toast notifications, shared clipboard scratchpad, file request system with drag-to-fulfill

---
