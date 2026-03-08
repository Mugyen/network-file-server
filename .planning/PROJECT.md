# WiFi File Server

## What This Is

A polished, cross-platform LAN file sharing tool that lets any device on the same network browse, share, preview, and request files through a modern web UI. Think AirDrop but browser-based, cross-platform, and feature-rich. Built with a React frontend and FastAPI backend — designed to be a real product others install and use.

## Core Value

Any device on the same WiFi network can instantly share files with zero setup — scan QR, drop files, done.

## Requirements

### Validated

- ✓ Basic file listing and browsing — existing
- ✓ File download — existing
- ✓ Single file upload — existing
- ✓ CLI with folder path argument — existing
- ✓ Local IP detection and display — existing

### Active

- [ ] Full rewrite with React UI + FastAPI backend
- [ ] QR code instant connect (feature #01)
- [ ] Cross-device clipboard sharing with real-time sync (feature #02)
- [ ] In-browser media preview — images, video, audio, PDF, code (feature #03)
- [ ] Drag-and-drop upload with progress bars, batch download/delete, folder navigation (feature #04)
- [ ] Dark mode with system detection (feature #18)
- [ ] Search, filter, and sort for file browser (feature #19)
- [ ] Real-time transfer notifications via WebSocket toasts (feature #20)
- [ ] File request system — request files from connected devices (feature #31)

### Out of Scope

- E2E encryption — deferred to v2, too complex for initial release
- WebRTC P2P transfers (#06) — v2+
- Secure tunnel / remote access (#07) — v2+
- Auto-sync (#09) — v2+
- Admin dashboard (#10) — v2+
- PWA / mobile app (#11, #29) — v2+
- Desktop tray app (#12) — v2+
- Plugin system (#13) — v2+
- File versioning (#15) — v2+
- Custom theming beyond dark mode (#18 pro) — v2+
- pip/brew/docker packaging — v1 just needs to work locally

## Context

- Existing codebase is ~200 lines of Flask + Jinja templates — functional but minimal
- Full rewrite to React + FastAPI gives a clean foundation for all 35 planned features
- WebSocket infrastructure is shared between clipboard sync, notifications, and file requests
- Target audience: general public who want easy LAN file sharing
- "Done" for v1 = works locally on the developer's LAN, solid and usable
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
| Full rewrite over incremental upgrade | Clean foundation for 35 planned features; Flask+Jinja won't scale | — Pending |
| React + FastAPI over Flask + htmx | Modern stack, better DX, reusable component model for complex features | — Pending |
| Defer E2E encryption to v2 | Touches every file operation, too complex for v1 | — Pending |
| WebSocket for real-time features | Shared infra for clipboard, notifications, and file requests | — Pending |
| No authentication in v1 | LAN tool — open access is a feature, not a bug | — Pending |

---
*Last updated: 2026-03-09 after initialization*
