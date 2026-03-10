# WiFi File Server

## What This Is

A polished, cross-platform file sharing tool that lets any device browse, upload, preview, and request files through a modern web UI with real-time collaboration and access control. Works on LAN (direct) or over the internet via remote mounts — a publicly hosted relay server that proxies to a client agent. Think AirDrop but browser-based, cross-platform, and feature-rich — with shared clipboard, file requests, media preview, expiring share links, device discovery, and remote mounting. Built with React + FastAPI + WebSocket.

## Current Milestone: v1.2 Remote Mounts

**Goal:** Enable file sharing over the internet by letting users mount their local filesystem through a public relay server, accessible via short code or QR — without requiring recipients to install anything.

**Target features:**
- Agent CLI command to mount a local directory through a remote server via WebSocket tunnel
- Lightweight relay server that routes browser requests to the correct agent by mount code
- Mount landing page with code entry and QR scan
- Per-mount password protection and TTL auto-expire (reuse existing infra)
- Existing LAN mode preserved unchanged

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

- [ ] Agent CLI command to mount local directory through remote server
- [ ] Relay server that proxies browser requests to agent via mount code
- [ ] Mount landing page with code entry and QR scan
- [ ] Per-mount password protection and TTL auto-expire
- [ ] Existing LAN mode preserved unchanged

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
- Per-user accounts / multi-password — deferred to v1.3+, build accounts layer on top of mounts
- HTTPS / TLS — certificate management is massive friction for LAN tool
- Persistent share links (survive restart) — in-memory is a feature, no stale links
- Containerization / K8S — keep deployment simple for now
- Server-side file caching — pure proxy model, no server storage
- Device allowlists / role-based permissions — deferred to accounts milestone

## Context

- Shipped v1.1 with ~13,150 LOC (6,966 Python + 6,184 TypeScript)
- v1.2 introduces a relay server + agent model for remote mounts over the internet
- Agent connects outbound to server via WebSocket; server proxies browser requests through tunnel
- Only the mounting device needs the CLI agent; consumers use browser only
- Deployment target: cloud function or spot VM (no containerization yet)
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
*Last updated: 2026-03-11 after v1.2 milestone start*
