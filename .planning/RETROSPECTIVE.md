# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.2 — Remote Mounts

**Shipped:** 2026-03-16
**Phases:** 4 | **Plans:** 11

### What Was Built
- Binary WebSocket tunnel protocol with 21-byte frame headers, UUID multiplexing, and per-stream backpressure
- Relay server with mount registry, landing page, error templates, and HTTP/WebSocket proxying
- Agent CLI (`network-file-server mount`) with auto-reconnect, QR display, and terminal status
- Password protection and TTL auto-expiry for remote mounts
- SPA dynamic relay prefix detection — all v1.0/v1.1 features work through relay
- WebSocket tunneling for clipboard, notifications, and device discovery through relay
- Upload streaming via chunked DATA frames (gap closure after UAT)
- Copy-to-clipboard with HTTP fallback, relay CLI entry point, LAN IP QR resolution

### What Worked
- Tunnel protocol as shared library (tunnel/) used by both relay and agent — clean separation
- ASGI transport for agent proxy — no network hop, all features work identically
- UAT → diagnose → plan gaps → execute gaps workflow caught 2 real bugs and 2 missing features
- Agent-initiated outbound WebSocket means no NAT/firewall issues
- Cookie path scoping per mount code — multiple mounts in same browser work independently

### What Was Inefficient
- Race condition in agent receive loop (open_stream inside spawned task vs before) broke ALL relay requests — caught by user in UAT, not by automated tests
- Server-info endpoint returned port 0 in remote mode — visible to user immediately but missed in planning
- QR code used localhost which doesn't work from phones — obvious in hindsight but required user feedback
- `navigator.clipboard` requires HTTPS — already solved for scratchpad textarea but not for copy button
- ROADMAP.md progress table was stale (phase 9 showed "1/2 In Progress" when actually complete)
- Gap closure agent got blocked on Bash permissions, requiring manual completion by orchestrator

### Patterns Established
- `_resolve_lan_url()`: replace localhost/127.0.0.1 with LAN IP in URLs for device access
- `execCommand("copy")` fallback when `navigator.clipboard` unavailable (HTTP-over-LAN)
- Stream registration before task spawn: `open_stream()` must happen in receive loop, not in handler
- Convenience scripts (`run_relay.sh`, `run_mount_server.sh`) with auto-rebuild on stale client dist
- `relay_url` in ServerConfig so server-info endpoint can construct correct mount URL

### Key Lessons
1. Race conditions between async task spawn and frame dispatch are invisible to unit tests — integration tests with real WebSocket frames would have caught this
2. When adding a new deployment mode (remote), audit ALL user-facing surfaces (QR code, server-info, clipboard API) for assumptions about localhost/LAN context
3. UAT on actual devices (phone) catches platform-specific issues (clipboard API, localhost QR) that desktop testing misses
4. Gap closure cycle (UAT → diagnose → plan → execute → re-verify) is the right workflow for hardening
5. Automated agents can get blocked on permissions — orchestrator should be ready to complete manually

### Cost Observations
- Model mix: sonnet for execution, opus for orchestration
- Notable: 2 gap closure plans + 6 additional bug fixes discovered during UAT verification
- Timeline: 5 days, most time spent on hardening and UAT rather than initial implementation

---

## Milestone: v1.1 — Share & Access Control

**Shipped:** 2026-03-11
**Phases:** 3 | **Plans:** 7

### What Was Built
- Password protection with bcrypt + itsdangerous session cookies, login page, and logout
- Read-only mode with backend enforcement on 10 write surfaces and frontend control hiding
- Receive mode / digital drop box with upload-only drag-and-drop interface
- Expiring share links with TTL selection, Jinja2 download/expired pages, auth bypass, and revocation
- Real-time device discovery panel with type icons and "You" badge

### What Worked
- itsdangerous reuse across auth tokens (Phase 5) and share link tokens (Phase 6) — planned ahead and it paid off
- Cookie-based auth was the right call — header-based would have broken `<a>` downloads and `<img>` previews
- Orthogonal mode guards (require_write_access vs require_full_access) made access control composable
- Jinja2 server-rendered share pages avoided requiring React SPA for link recipients
- DevicesPanel followed ShareLinksPanel slide-out pattern — UI consistency for free

### What Was Inefficient
- Auth middleware initially blocked SPA HTML shell, preventing login page from rendering — caught in UAT, not tests
- Integration tests tested the wrong behavior (expected 401 on `/` which was actually a bug)
- Scratchpad was completely hidden in read-only mode instead of being read-only — caught in manual testing
- Session cookies didn't persist across tabs because frontend didn't probe for existing valid sessions
- TypeScript `enum` broke on TS 5.8+ with `erasableSyntaxOnly` — had to convert to const object

### Patterns Established
- Auth middleware should only gate `/api/*` paths; SPA and static files pass through freely
- Frontend session probe: on load, probe a gated endpoint to detect valid existing session cookie
- `readOnly` prop cascade from App → panels → cards for conditional write-control hiding
- `run.sh` builds frontend then starts server — single command for users

### Key Lessons
1. UAT catches real bugs that unit/integration tests miss — the auth middleware bug was invisible to tests because tests hit API directly
2. Test the user's actual flow (load page → see UI), not just the API response codes
3. When adding access modes, enumerate ALL surfaces (not just routes — include SPA serving, static files, WebSocket)
4. `const` objects with `as const` are the TS 5.8+ compatible replacement for enums

### Cost Observations
- Model mix: balanced profile
- Notable: 3 UAT bugs found and fixed in-session (auth middleware, session persistence, read-only clipboard)

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-09
**Phases:** 4 | **Plans:** 13 | **Tasks:** ~29

### What Was Built
- FastAPI backend with path traversal guard, file management, search, preview, and WebSocket infrastructure
- React + Tailwind CSS v4 SPA with file browser, upload, preview modal, dark mode, clipboard, file requests
- QR code discovery (ASCII terminal + SVG web) for zero-setup device connection
- Real-time collaboration: toast notifications, shared clipboard scratchpad, file request system

### What Worked
- Coarse granularity (4 phases instead of 7) kept overhead low and momentum high
- TDD on backend plans (RED tests before GREEN implementation) caught path traversal edge cases early
- Shared WebSocket ConnectionManager made Phase 4 features (notifications, clipboard, requests) composable
- Consistent service/router/schema layering on backend made each plan predictable
- Average plan execution ~5min — tight feedback loops

### What Was Inefficient
- Phase 1 plan checkboxes in ROADMAP.md were never updated to [x] (cosmetic, but inconsistent with Phases 2-4)
- Some summary-extract fields (one_liner) were not populated in SUMMARY.md files — tooling gap
- Velocity tracking only covered Phases 1-3 in STATE.md; Phase 4 metrics were appended separately

### Patterns Established
- XHR for upload progress (fetch lacks upload.onprogress)
- useRef for WebSocket instances and drag counters to avoid stale closures
- Native URLSearchParams + pushState for simple path navigation (no React Router)
- Tailwind v4 @custom-variant for dark mode with FOUC prevention inline script
- JSON file persistence for clipboard/requests data (simple, no database needed for LAN tool)
- Device identity via random adjective+animal names in localStorage

### Key Lessons
1. Starlette's FileResponse handles Range requests natively — no custom 206 streaming needed
2. PrismLight with individual language imports keeps bundle size manageable for syntax highlighting
3. Textarea-based scratchpad is the correct approach for HTTP LAN tools (Clipboard API needs HTTPS)
4. ConflictDialog should force user choice (overwrite/rename/skip) with no cancel — prevents ambiguous state

### Cost Observations
- Model mix: balanced profile (opus for planning/research, sonnet for execution)
- Sessions: ~4 sessions across 1 day
- Notable: entire v1.0 MVP built in ~1.1 hours of execution time

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 4 | Initial release — coarse granularity, TDD backend, rapid frontend |
| v1.1 | ~3 | 3 | Added UAT workflow — caught 3 real bugs invisible to automated tests |
| v1.2 | ~5 | 4 | Gap closure cycle (UAT → diagnose → plan → execute) matured; device testing essential |

### Top Lessons (Verified Across Milestones)

1. Coarse phase granularity (fewer, larger phases) reduces planning overhead without sacrificing quality
2. TDD on API endpoints catches edge cases early and provides confidence for frontend integration
3. UAT with real user testing catches integration bugs that automated tests miss — verified across all 3 milestones
4. Cookie-based auth is mandatory for browser tools with `<a href>` downloads and `<img src>` previews
5. Test on actual target devices (phones) — desktop browsers hide platform-specific issues (clipboard API, localhost URLs)
6. When adding new deployment modes, audit ALL user-facing surfaces for context assumptions
