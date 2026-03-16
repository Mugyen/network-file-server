# Phase 11: Remote Access and Hardening - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Remote mounts support password protection via `--password`, auto-expiry via `--ttl`, and the React SPA works seamlessly through the relay proxy including all real-time WebSocket features. No new capabilities beyond what's scoped in ACCS-01, ACCS-02, RMUI-01, RMUI-02.

</domain>

<decisions>
## Implementation Decisions

### Password flow through relay
- Auth enforced agent-side only — relay is fully transparent and auth-unaware
- Reuse existing `--password` flag for mount subcommand — same flag as LAN mode, passed to `create_app()` which already handles bcrypt + itsdangerous
- Cookie path scoped to `/m/{code}/` so different mounts get isolated sessions on the same relay domain
- Login page reuses existing `LoginPage.tsx` identically — no mount-specific adaptations

### TTL expiry enforcement
- Agent-side only — agent tracks its own TTL timer, sends clean disconnect to relay when expired, then exits
- `--ttl` flag accepts human-readable durations: `30m`, `2h`, `1d` — agent parses into seconds
- Terminal shows countdown of remaining time next to mount info, updating periodically: "Expires in 1h 23m"
- Expired mounts show relay's existing error page from Phase 9 (no custom expiry page)

### SPA base URL injection
- Runtime URL detection: SPA reads `window.location.pathname` at startup, extracts `/m/{code}` prefix if present
- `API_BASE` becomes dynamic: `/api` in LAN mode, `/m/{code}/api` in remote mode
- Relay strips `/m/{code}` prefix before proxying to agent — agent's ASGI app sees clean `/api/*` paths unchanged
- Static assets served through relay proxy using relative paths in HTML (e.g., `./assets/main.js`)
- Subtle "Remote" pill badge in header, matching existing `[Read Only]` / `[Protected]` badge pattern from Phase 5

### WebSocket tunneling for real-time
- Relay tunnels WS upgrade requests through the existing tunnel infrastructure — browser opens WS to `/m/{code}/ws`, relay bridges frames to agent
- New tunnel frame types: `WS_OPEN`, `WS_DATA`, `WS_CLOSE` — WS connections are long-lived and bidirectional, don't fit HTTP's OPEN/DATA/CLOSE pattern
- All real-time features work in remote mode: clipboard sync, transfer notifications, file requests, device discovery — full parity with LAN mode
- SPA derives WebSocket URL from `window.location` using same runtime detection as API base: `ws://relay/m/{code}/ws`

### Claude's Discretion
- TTL countdown update interval (every minute, every 30s, etc.)
- Human-readable duration parsing implementation details
- Exact `WS_OPEN`/`WS_DATA`/`WS_CLOSE` frame type byte values and header format
- How relay bridges WS frames bidirectionally through the tunnel connection
- Error handling when WS tunnel connection drops mid-session

</decisions>

<specifics>
## Specific Ideas

- Cookie scoping to `/m/{code}/` is critical — without it, authenticating on one mount would leak session to another mount on the same relay
- Relay stripping `/m/{code}` prefix means agent code (and all v1.0/v1.1 features) work without any path awareness changes
- "Remote" badge follows the exact same pattern as existing mode badges in `ModeBadges.tsx`
- TTL countdown in terminal mirrors the existing "uptime" display from Phase 10's connected status

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `server/app/middleware/auth_middleware.py`: Pure ASGI auth middleware — already gates `/api/*`, needs cookie path adjustment for remote mode
- `server/app/services/auth_service.py`: bcrypt password hashing + itsdangerous session tokens — fully reusable
- `server/app/config.py:ServerConfig`: Already has `password_hash` field — agent passes it through to `create_app()`
- `client/src/api/client.ts:API_BASE`: Currently `"/api"` — needs to become dynamic based on URL detection
- `client/src/components/ModeBadges.tsx`: Pill badge component for mode indicators — extend with "Remote" badge
- `client/src/components/LoginPage.tsx`: Full login page component — reuse as-is for remote mounts
- `tunnel/enums.py:FrameType`: Existing frame types (OPEN, DATA, CLOSE, CANCEL, ERROR) — extend with WS_OPEN, WS_DATA, WS_CLOSE
- `relay/app/routers/mount_proxy.py`: HTTP proxy router — extend with WS upgrade handling

### Established Patterns
- Cookie-based auth with itsdangerous — chosen specifically because `<a href>` downloads and `<img src>` previews bypass custom headers
- Relay path stripping already partially implemented — relay routes `/m/{code}/*` and forwards the `/*` part
- Agent in-process ASGI transport via httpx — `create_app()` handles all features, agent just proxies
- `_build_parser()` / `_parse_args()` pattern for CLI flags — mount subcommand extends existing parser

### Integration Points
- `agent/connection.py:connect_and_serve`: Needs `--password` and `--ttl` params passed through to `create_app()` and timer setup
- `relay/app/routers/mount_proxy.py`: Needs WS upgrade detection and frame bridging
- `tunnel/connection.py:TunnelConnection`: Needs WS frame type handling in send/receive loops
- `client/src/App.tsx`: Needs remote mode detection to set API base and show badge
- `client/src/hooks/useWebSocket` (or equivalent): Needs dynamic WS URL based on mount context

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-remote-access-and-hardening*
*Context gathered: 2026-03-11*
