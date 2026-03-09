# WiFi File Server

## What This Is

A polished, cross-platform LAN file sharing tool that lets any device on the same network browse, upload, preview, and request files through a modern web UI with real-time collaboration. Think AirDrop but browser-based, cross-platform, and feature-rich — with shared clipboard, file requests, and media preview. Built with React + FastAPI + WebSocket.

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

### Active

(None — define for next milestone with `/gsd:new-milestone`)

### Out of Scope

- E2E encryption — deferred to v2, too complex for initial release
- WebRTC P2P transfers — v2+
- Secure tunnel / remote access — v2+, LAN-only is core value
- Auto-sync (#09) — fundamentally different from file sharing
- Admin dashboard — no auth in v1, no admin role needed
- PWA / mobile app — v2+, web works well on mobile
- Desktop tray app — separate project (Electron/Tauri)
- Plugin system — over-engineering for v1
- File versioning — needs database, filesystem doesn't support natively
- Custom theming beyond dark mode — v2+
- pip/brew/docker packaging — v1 just needs to work locally

## Context

- Shipped v1.0 with ~9,600 LOC (4,700 Python + 4,900 TypeScript)
- Tech stack: React + Tailwind CSS v4 (frontend), FastAPI + uvicorn (backend), WebSocket (real-time)
- WebSocket infrastructure shared between clipboard sync, notifications, and file requests
- Target audience: general public who want easy LAN file sharing
- v1.0 built in a single day — 4 phases, 13 plans, ~29 tasks
- Codebase map available at `.planning/codebase/`

## Constraints

- **Tech stack**: React (frontend) + FastAPI (backend) + WebSocket (real-time features)
- **Dependency management**: uv for Python
- **Runtime**: Python 3.11+, Node for frontend build
- **Network**: LAN-only for v1 (no internet required for operation)
- **No auth for v1**: Open access on LAN is intentional for ease of use

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full rewrite over incremental upgrade | Clean foundation for 35 planned features; Flask+Jinja won't scale | ✓ Good — clean codebase, all features delivered |
| React + FastAPI over Flask + htmx | Modern stack, better DX, reusable component model for complex features | ✓ Good — component reuse across all phases |
| Defer E2E encryption to v2 | Touches every file operation, too complex for v1 | ✓ Good — correct scope for v1 |
| WebSocket for real-time features | Shared infra for clipboard, notifications, and file requests | ✓ Good — ConnectionManager shared across 3 features |
| No authentication in v1 | LAN tool — open access is a feature, not a bug | ✓ Good — zero-setup is core value |
| Starlette FileResponse for preview | Native Range request support eliminates custom 206 streaming code | ✓ Good — zero custom streaming code |
| PrismLight tree-shaking | 23 individual language imports vs full Prism — keeps bundle manageable | ✓ Good |
| Tailwind v4 @custom-variant dark mode | CSS-first dark mode with FOUC prevention inline script | ✓ Good |
| 3-state theme toggle | SYSTEM/DARK/LIGHT cycle instead of simple on/off | ✓ Good |
| XHR for upload progress | fetch() lacks upload.onprogress support | ✓ Good — reliable progress bars |
| Native URLSearchParams navigation | No React Router needed for simple path-based navigation | ✓ Good — minimal dependency |
| Textarea scratchpad over Clipboard API | Clipboard API requires HTTPS; textarea works on HTTP LAN | ✓ Good — correct for LAN context |

---
*Last updated: 2026-03-09 after v1.0 milestone*
