# WiFi File Server

## What This Is

A polished, cross-platform LAN file sharing tool that lets any device on the same network browse, upload, preview, and request files through a modern web UI with real-time collaboration and access control. Think AirDrop but browser-based, cross-platform, and feature-rich — with shared clipboard, file requests, media preview, expiring share links, and device discovery. Built with React + FastAPI + WebSocket.

## Core Value

Any device on the same WiFi network can instantly share files with zero setup — scan QR, drop files, done.

## Requirements

### Validated

- ✓ Basic file listing and browsing — v1.0
- ✓ File download — v1.0
- ✓ Single file upload — v1.0
- ✓ CLI with folder path argument — v1.0
- ✓ Local IP detection and display — v1.0
- ✓ In-browser media preview — images, video, audio, PDF, code — v1.0
- ✓ Dark mode with system detection — v1.0
- ✓ Search, filter, and sort for file browser — v1.0
- ✓ Full rewrite with React UI + FastAPI backend — v1.0
- ✓ QR code instant connect — v1.0
- ✓ Cross-device clipboard sharing with real-time sync — v1.0
- ✓ Drag-and-drop upload with progress bars, batch download/delete, folder navigation — v1.0
- ✓ Real-time transfer notifications via WebSocket toasts — v1.0
- ✓ File request system — request files from connected devices — v1.0
- ✓ Password protection via `--password` CLI flag — v1.1
- ✓ Read-only mode via `--read-only` CLI flag — v1.1
- ✓ Receive mode / digital drop box via `--receive` CLI flag — v1.1
- ✓ Expiring share links with TTL selection and clean download pages — v1.1
- ✓ Share links bypass password protection — v1.1
- ✓ Share link listing and revocation for server operator — v1.1
- ✓ Real-time device discovery with type icons and self-identification — v1.1

### Active

- [ ] Rich terminal UI dashboard
- [ ] Network speed test

### Out of Scope

- E2E encryption — deferred to v2, too complex for initial release
- WebRTC P2P transfers — v2+
- Secure tunnel / remote access — v2+, LAN-only is core value
- Auto-sync — fundamentally different from file sharing
- PWA / mobile app — v2+, web works well on mobile
- Desktop tray app — separate project (Electron/Tauri)
- Plugin system — over-engineering
- File versioning — needs database, filesystem doesn't support natively
- Custom theming beyond dark mode — v2+
- pip/brew/docker packaging — future concern
- Per-user accounts / multi-password — contradicts "zero setup" core value
- HTTPS / TLS — certificate management is massive friction for LAN tool
- Persistent share links (survive restart) — in-memory is a feature, no stale links

## Context

- Shipped v1.1 with ~13,150 LOC (6,966 Python + 6,184 TypeScript)
- Tech stack: React + Tailwind CSS v4 (frontend), FastAPI + uvicorn (backend), WebSocket (real-time)
- WebSocket infrastructure shared between clipboard sync, notifications, file requests, and device discovery
- Target audience: general public who want easy LAN file sharing
- v1.0 built in 1 day, v1.1 in 3 days — 7 phases, 20 plans total
- Auth uses cookie-based sessions (bcrypt + itsdangerous), not header-based
- Share links use Jinja2 server-rendered pages (no SPA needed for recipients)
- `run.sh` builds frontend and starts server in one command

## Constraints

- **Tech stack**: React (frontend) + FastAPI (backend) + WebSocket (real-time features)
- **Dependency management**: uv for Python
- **Runtime**: Python 3.11+, Node for frontend build
- **Network**: LAN-only (no internet required for operation)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full rewrite over incremental upgrade | Clean foundation for planned features; Flask+Jinja won't scale | ✓ Good — clean codebase, all features delivered |
| React + FastAPI over Flask + htmx | Modern stack, better DX, reusable component model for complex features | ✓ Good — component reuse across all phases |
| WebSocket for real-time features | Shared infra for clipboard, notifications, file requests, devices | ✓ Good — ConnectionManager shared across 4 features |
| Cookie-based auth over header-based | `<a href>` downloads and `<img src>` previews bypass custom headers | ✓ Good — correct for browser context |
| Pure ASGI middleware for auth | BaseHTTPMiddleware deprecated; pure ASGI is more performant | ✓ Good |
| itsdangerous for tokens | Reusable for both session tokens and share link tokens | ✓ Good — reused across Phase 5 and 6 |
| Jinja2 for share pages | Recipients don't need React SPA; server-rendered is simpler and faster | ✓ Good |
| Auth middleware gates only /api/* | SPA must load for LoginPage to render; non-API paths pass through | ✓ Good — fixed after UAT caught the bug |
| Starlette FileResponse for preview | Native Range request support eliminates custom 206 streaming code | ✓ Good |
| XHR for upload progress | fetch() lacks upload.onprogress support | ✓ Good — reliable progress bars |
| Textarea scratchpad over Clipboard API | Clipboard API requires HTTPS; textarea works on HTTP LAN | ✓ Good — correct for LAN context |

---
*Last updated: 2026-03-11 after v1.1 milestone*
