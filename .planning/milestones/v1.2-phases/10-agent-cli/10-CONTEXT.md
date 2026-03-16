# Phase 10: Agent CLI - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

CLI command to mount a local directory through the relay server, making files accessible to anyone with the mount code. The agent connects outbound to the relay via WebSocket, registers a mount, and proxies tunneled HTTP requests to a local FastAPI server using `create_app()`. Password protection, TTL expiry, and SPA adaptation are Phase 11.

</domain>

<decisions>
## Implementation Decisions

### CLI structure
- Subcommand pattern: `wifi-file-server mount ./files --server <url>`
- Existing bare positional `wifi-file-server ./files` stays unchanged for LAN mode (no breaking change)
- `--server` flag is required for mount subcommand (relay URL)
- `--name` flag is optional (human-readable mount name, defaults to folder name)
- Mount code assigned by relay server (agent does not request a specific code)

### Request proxying
- In-process ASGI transport: call `create_app()` in-process, use `httpx.AsyncClient` with `ASGITransport` — no port binding, no network hop
- Stream response bodies back through tunnel as DATA frames (essential for large file downloads)
- Stream request bodies from tunnel frames as async iterator to httpx (essential for large uploads)
- Handle CANCEL frames from relay — abort in-flight httpx request and clean up the stream when browser disconnects

### Terminal UX
- After successful mount: display mount URL, QR code (reuse `qr_service`), mount code, sharing folder, relay URL, and status line
- Minimal activity indicators: show brief line per proxied request (e.g., `GET /api/files 200`)
- Display running request count and connection duration (uptime)
- Graceful shutdown on Ctrl+C: print "Unmounting...", send clean disconnect to relay, deregister mount, then exit

### Reconnection behavior
- Auto-reconnect with exponential backoff and jitter, unlimited retries (capped at ~60s backoff)
- Request same mount code on reconnect — relay re-registers if code is still available
- If old code is rejected (reassigned), accept a new code and update terminal display with new URL/QR
- Status line updates during reconnection: "Reconnecting (attempt N, next in Xs)..." then "Connected (reconnected)"

### Claude's Discretion
- Backoff algorithm parameters (base, cap, jitter range)
- Agent module/package structure within the project
- httpx client configuration details
- Mount registration control message format (JSON text frame details)
- How to detect and handle relay server being completely unreachable vs code rejection

</decisions>

<specifics>
## Specific Ideas

- Mount URL format: `https://relay.example.com/m/{code}` — matches relay's existing `/m/{code}/*` routing
- QR code should encode the full mount URL, not just the code
- Activity log should be one-line-per-request, not verbose — similar to uvicorn's access log format
- Reconnect should be invisible to browser users if they retry — same URL works once agent reconnects with same code

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `server/app/main.py:create_app()`: Full LAN FastAPI app factory — agent calls this in-process via ASGITransport
- `server/app/services/qr_service.py:generate_ascii_qr()`: ASCII QR code generation — reuse for mount URL display
- `server/app/services/network_service.py:detect_primary_lan_ip()`: Not needed for remote mode but same output pattern
- `tunnel/connection.py:TunnelConnection`: Stream multiplexing, heartbeat, backpressure — agent wraps its WebSocket with this
- `tunnel/frames.py`: serialize_frame/deserialize_frame — agent uses these for building response frames
- `tunnel/enums.py:FrameType`: OPEN/DATA/CLOSE/CANCEL/ERROR — agent responds to OPEN with DATA+CLOSE

### Established Patterns
- argparse-based CLI in `server/app/cli.py` with `_build_parser()` and `main()` — mount subcommand extends this
- `ServerConfig` dataclass + `set_server_config()` singleton pattern for config injection
- `relay/app/routers/agent_ws.py`: Relay-side WebSocket endpoint at `/agent/ws?code=...` — agent connects here
- `relay/app/services/mount_registry.py`: `register(code, conn)` / `deregister(code)` — agent's mount lifecycle

### Integration Points
- Agent connects to relay's `/agent/ws` WebSocket endpoint
- Mount registration via JSON text control message through TunnelConnection
- Agent receives OPEN frames (with HTTP method, path, headers), forwards to local ASGI app, sends back DATA/CLOSE frames
- httpx needs to move from dev to production dependencies (noted in STATE.md)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-agent-cli*
*Context gathered: 2026-03-11*
