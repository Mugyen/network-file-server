# Milestones

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
