# Phase 15: UX Polish and Drop Box - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

The relay gets a production-ready public face: a polished landing page with social previews, connection status overlays in the SPA, an always-on public drop box mount, and per-file upload TTLs with auto-deletion. This also includes updating the Dockerfile and deploy script for VPS + persistent disk deployment (replacing the Cloud Run ephemeral model).

</domain>

<decisions>
## Implementation Decisions

### Landing page design
- Hero section layout (not minimal card): large heading, tagline, how-it-works steps, code form, drop box link, GitHub link
- How-it-works strip between tagline and code form: 3 horizontal steps ("1. Run the agent  2. Share your code  3. Browse files")
- Jinja2 template extending base.html — overrides card layout with wider hero container
- OG meta tags: og:title, og:description, og:image on all relay pages
- OG image: generated SVG/PNG card with project name and tagline, checked into repo as a static asset

### Connection status overlays
- Banner + disabled UI pattern for BOTH offline (503) and expired (410) states
- Offline: persistent banner at top saying "Host Offline — reconnecting...", file list greyed out and non-interactive
- Expired: persistent banner at top saying "Mount Expired", file list greyed out, "Back to home" link
- Detection: REST polling via `GET /m/{code}/status` endpoint every 30s, returns `{status: "online"|"offline"|"expired"}`
- Auto-recovery on reconnect: when status poll returns "online" again, banner disappears and file list refreshes automatically
- No auto-recovery for expired (terminal state)

### Drop box architecture
- Drop box = always-connected mount, not a special case
- In-process FastAPI mount: relay imports server package's `create_app()` and mounts it for the reserved drop box code
- mount_proxy recognizes the reserved code and routes to the local server app instead of tunneling
- Full server API supported (browse, search, preview, download, upload, clipboard, etc.) — not receive-mode-only
- Register drop box as a first-class mount record in SQLite: status ONLINE, TTL null (never expires), reserved code
- Reserved mount code prevents external agents from claiming it (configurable via env var, default "dropbox")
- Dockerfile updated to include server package dependency for drop box import

### Deployment model shift (VPS + persistent disk)
- Deploy target: VPS with persistent disk, not Cloud Run ephemeral instances
- Configurable data directory: `data_dir` in config.yaml (default `/data/`), env var override `RELAY_DATA_DIR`
- SQLite DB at `{data_dir}/mounts.db`, drop box files at `{data_dir}/dropbox/`
- All state persists across reboots — no data loss on restart
- Transaction-like operations: ensure partial state can't occur on crash
- Update Dockerfile + deploy script for VPS deployment (docker-compose or similar with persistent volume mount)

### File TTL picker & expiry UX
- Dropdown in upload dialog: "Expires in" with options 1h, 6h, 1d (default), 7d, Never
- Applies per-batch (all files in one upload get the same TTL)
- Per-file TTL metadata stored in SQLite: `file_ttl` table with (mount_code, file_path, expires_at, created_at)
- Expiry badge in file listing: countdown text ("2h left", "3d left"), orange when <6h remaining, red when <1h
- Files without TTL show no badge
- Expired file deletion: background sweep deletes files and broadcasts WebSocket toast notification to connected browsers
- On relay boot: auto-delete expired drop box files and log each deletion at INFO level
- For agent-backed mounts: mark expired files as pending, agent CLI prompts user on reconnect to keep or delete

### Claude's Discretion
- Exact landing page copy and styling beyond the layout decision
- Status endpoint response format details
- Banner component styling (colors, animation, exact wording)
- File TTL sweep interval
- How the server package is mounted within mount_proxy (ASGI sub-application vs request forwarding)
- docker-compose.yml structure and volume configuration
- SVG/PNG OG image design

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `relay/templates/base.html`: Jinja2 base template with dark mode, viewport meta, shared styles — landing page extends this
- `relay/templates/landing.html`: Existing landing page with code form and redirect — enhance with hero section
- `relay/app/routers/landing.py`: Landing route handler — add OG meta tags
- `client/src/components/DropBoxPage.tsx`: Upload-only UI for receive mode — reference for drop box, but full app will be used instead
- `client/src/components/ConnectionStatus.tsx`: Green/red dot indicator — extend with banner overlay
- `client/src/hooks/useWebSocket.ts`: WebSocket connection with reconnect logic — toast notifications for file deletion
- `client/src/hooks/useToast.ts`: Toast state management with auto-dismiss — reuse for file expiry toasts
- `client/src/api/client.ts:handleRelayError()`: Currently redirects on 503/410 — replace with status state management
- `server/app/main.py:create_app()`: Server app factory — import directly for drop box mount
- `relay/app/services/sqlite_registry.py`: SQLite mount registry — register drop box as a mount record
- `relay/app/services/ttl_sweep.py`: Background TTL sweep — extend for file TTL sweep
- `relay/app/config.py`: RelayConfig with YAML + env vars — add data_dir, dropbox_code fields

### Established Patterns
- Jinja2 templates extend base.html with block overrides
- Config module: YAML defaults + env var overrides via load_config()
- Background asyncio tasks via FastAPI lifespan (TTL sweep pattern)
- Module-level singleton: get_registry/set_registry
- REST polling for status (decided in STATE.md: "Connection status via REST polling every 30s")
- Toast notifications via WebSocket broadcast

### Integration Points
- `relay/app/routers/mount_proxy.py`: Route reserved code to local server app instead of tunnel
- `relay/app/routers/landing.py`: Enhance template with hero section and OG tags
- `relay/templates/base.html`: Add OG meta tag blocks
- `relay/app/main.py:create_relay_app()`: Initialize drop box server app, register in SQLite, start file TTL sweep
- `relay/app/services/sqlite_registry.py`: Add reserved code protection (reject external agents claiming reserved codes)
- `client/src/api/client.ts`: Add status polling, replace redirect behavior with state-based overlays
- `client/src/hooks/useUpload.ts`: Add TTL parameter to upload requests
- `server/app/routers/files.py`: Accept TTL query param on upload, store in file_ttl table
- `Dockerfile`: Include server package, add VOLUME for /data/
- `deploy_relay.sh`: Update for VPS deployment with docker-compose

</code_context>

<specifics>
## Specific Ideas

- "Think of the dropbox as an always connected mount" — not a special case, just a mount that's always online and backed by a local server app
- "Instead of Cloud Run, think of this as deployed on a VPS + persistent disk" — persistent state is the norm, not the exception
- "Actions should be transaction-like and all state persists so that a reboot doesn't affect any state" — design for spot VM flakiness
- The server package import for drop box means the Dockerfile needs both relay and server packages
- Status polling at 30s intervals was already decided as the connection status approach (from STATE.md decisions)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-ux-polish-and-drop-box*
*Context gathered: 2026-04-02*
