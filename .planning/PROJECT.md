# WiFi File Server

## What This Is

A polished, cross-platform file sharing tool that lets any device browse, upload, preview, and request files through a modern web UI with real-time collaboration and access control. Works on LAN (direct) or over the internet via remote mounts — a relay server proxies to a client agent through a binary WebSocket tunnel. Think AirDrop but browser-based, cross-platform, and feature-rich — with shared clipboard, file requests, media preview, expiring share links, device discovery, and remote mounting. Built with React + FastAPI + WebSocket.

## Core Value

Any device can instantly share files with zero setup — scan QR, drop files, done. Works on LAN or over the internet.

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
- ✓ Agent CLI to mount local directory through remote relay server — v1.2
- ✓ Relay server proxying browser requests to agent via mount code — v1.2
- ✓ Mount landing page with code entry and QR scan — v1.2
- ✓ Per-mount password protection and TTL auto-expire — v1.2
- ✓ SPA works identically through relay (all features preserved) — v1.2
- ✓ WebSocket tunneling for real-time features through relay — v1.2
- ✓ Large file upload streaming through relay — v1.2
- ✓ QR code resolves localhost to LAN IP for phone access — v1.2

### Active

(None — ready for next milestone planning)

### Out of Scope

- E2E encryption — deferred to v2, too complex for initial release
- WebRTC P2P transfers — v2+
- Auto-sync — fundamentally different from file sharing
- PWA / mobile app — v2+, web works well on mobile
- Desktop tray app — separate project (Electron/Tauri)
- Plugin system — over-engineering
- File versioning — needs database, filesystem doesn't support natively
- Custom theming beyond dark mode — v2+
- pip/brew/docker packaging — future concern
- Per-user accounts / multi-password — deferred to v1.3+
- HTTPS / TLS — certificate management is massive friction for LAN tool
- Persistent share links (survive restart) — in-memory is a feature, no stale links
- Containerization / K8S — keep deployment simple for now
- Server-side file caching — pure proxy model, no server storage
- Device allowlists / role-based permissions — deferred to accounts milestone

## Context

- Shipped v1.2 with ~19,500 LOC (13,098 Python + 6,400 TypeScript)
- Three milestones shipped: v1.0 MVP, v1.1 Share & Access Control, v1.2 Remote Mounts
- 11 phases, 31 plans total across all milestones
- Tech stack: React + Tailwind CSS v4 (frontend), FastAPI + uvicorn (backend), WebSocket (real-time)
- WebSocket infrastructure shared between clipboard sync, notifications, file requests, device discovery, and relay tunneling
- Binary tunnel protocol with 21-byte frame headers, UUID multiplexing, and per-stream backpressure
- Relay server runs separately from LAN server; agent connects outbound via WebSocket
- Auth uses cookie-based sessions (bcrypt + itsdangerous), scoped per mount code
- `run_relay.sh` and `run_mount_server.sh` auto-rebuild frontend and start services
- Target audience: anyone who wants easy file sharing — LAN or internet

## Constraints

- **Tech stack**: React (frontend) + FastAPI (backend) + WebSocket (real-time features)
- **Dependency management**: uv for Python
- **Runtime**: Python 3.11+, Node for frontend build
- **Network**: LAN or internet via relay tunnel

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
| Binary WebSocket tunnel protocol | Efficient multiplexing over single connection; 21-byte header keeps overhead minimal | ✓ Good — handles concurrent requests cleanly |
| Agent-initiated outbound WebSocket | No NAT traversal needed; agent connects to relay, not the other way around | ✓ Good — works behind any firewall |
| ASGI transport for local proxy | Agent proxies tunnel requests to local FastAPI via httpx ASGITransport — no network hop | ✓ Good — all features work identically |
| Chunked DATA frames for uploads | Stream request bodies as multiple frames to avoid exceeding 64KB frame limit | ✓ Good — fixed after UAT caught the bug |
| execCommand fallback for clipboard | navigator.clipboard requires HTTPS; HTTP-over-LAN on mobile needs fallback | ✓ Good — correct for LAN context |
| LAN IP resolution in QR codes | localhost in QR code doesn't work from phones; detect and substitute LAN IP | ✓ Good — phones can now scan and connect |

---
*Last updated: 2026-03-16 after v1.2 milestone completion*
