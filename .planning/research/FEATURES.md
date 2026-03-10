# Feature Landscape: v1.2 Remote Mounts

**Domain:** Remote file sharing via relay tunnel -- WebSocket proxy, mount lifecycle, access control
**Researched:** 2026-03-11
**Confidence:** HIGH (verified against ngrok, Cloudflare Tunnel, localtunnel, exposr, and community implementations)
**Scope:** v1.2 features ONLY. v1.0 (file CRUD, preview, clipboard, real-time) and v1.1 (password, read-only, receive, share links, device discovery) are shipped and validated.

## Context

v1.1 shipped with access control (password, read-only, receive mode), expiring share links, and device discovery. v1.2 introduces internet-accessible file sharing via a relay server model: a CLI agent on the user's machine connects outbound to a public relay server via WebSocket, and the relay proxies browser HTTP requests through the tunnel to the agent. Recipients need only a browser and a short mount code.

Existing infrastructure that v1.2 features build on:
- **CLI** (`server/app/cli.py`): argparse with `folder`, `--port`, `--host`, `--password`, `--read-only`, `--receive` flags
- **Config** (`server/app/config.py`): `ServerConfig` with `shared_folder`, `port`, `password_hash`, `read_only`, `receive`
- **WebSocket** (`server/app/services/connection_manager.py`): `ConnectionManager` with device tracking, broadcast, send_to
- **Auth middleware** (`server/app/middleware/auth_middleware.py`): cookie-based session auth with bcrypt
- **Mode guard** (`server/app/middleware/mode_guard.py`): enforces read-only/receive mode restrictions
- **Share links** (`server/app/services/share_service.py`): itsdangerous-based expiring tokens
- **Enums** (`server/app/models/enums.py`): `WSMessageType`, `ToastType`, `ShareTTL`, `DeviceType`

---

## How Relay Tunnel Systems Work

Based on analysis of ngrok, Cloudflare Tunnel, localtunnel, serveo, exposr, and community implementations ("Building your own Ngrok in 130 lines", "Reverse Proxying over WebSockets", exposrd):

### The Standard Architecture

```
[Browser] --HTTP--> [Relay Server] --WebSocket tunnel--> [Agent CLI] --localhost--> [Local File Server]
```

1. **Agent connects outbound** to relay server via WebSocket. No port forwarding needed. The agent initiates the connection, so it works behind NAT/firewalls.
2. **Relay assigns a public identifier** (subdomain, short code, or path) to the agent's tunnel.
3. **Browser requests** arrive at the relay server addressed to the mount's identifier.
4. **Relay serializes** the HTTP request (method, headers, path, body) into a WebSocket message with a correlation ID (UUID).
5. **Agent deserializes** the request, forwards it to the local server (localhost), collects the response, and sends it back over WebSocket with the same correlation ID.
6. **Relay deserializes** the response and writes it back to the browser's HTTP connection.

### Key Design Decisions in the Ecosystem

| Decision | ngrok | Cloudflare Tunnel | localtunnel | This Project |
|----------|-------|-------------------|-------------|--------------|
| Identifier | Random subdomain (`abc123.ngrok.io`) | Random subdomain (`xyz.trycloudflare.com`) | Random or requested subdomain | Short alphanumeric mount code (6-8 chars) |
| Transport | Custom multiplexed TCP | HTTP/2 + QUIC | TCP proxy | WebSocket (matches existing infra) |
| Auth | API key + account | Cloudflare account | None | Per-mount password (reuse v1.1 auth) |
| Reconnection | Auto with exponential backoff | Auto with built-in HA | Manual restart | Auto with exponential backoff + jitter |
| Heartbeat | Ping every 10s, 10s tolerance | Built into protocol | None | Ping/pong every 20s (websockets library default) |
| Concurrency | Multiplexed (many requests on one conn) | Multiplexed | One TCP conn per request | Multiplexed via correlation IDs on single WebSocket |

---

## Table Stakes (Users Expect These)

For a tool that claims "share files over the internet via short code," these are non-negotiable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Agent CLI mount command** | The agent is how users expose their local folder. `wifi-file-server mount ./files --server relay.example.com` must work in one command. Every tunnel tool (ngrok, cloudflared, lt) uses a single CLI command to start. | MEDIUM | New CLI subcommand. Connects to relay via WebSocket, registers mount, proxies requests to local FastAPI server. Reuses existing `ServerConfig` and file serving infra. |
| **Relay server with mount routing** | The relay accepts agent connections and routes browser requests to the correct agent by mount code. This IS the product -- without it there's nothing. | HIGH | Separate FastAPI application. Maintains a registry of active mounts (mount_code -> WebSocket connection). Routes incoming HTTP by mount code prefix. |
| **Short mount code** | Users share files by giving someone a 6-8 character code (like `abc123`). This is the UX differentiator vs full URLs. AirDrop uses pairing codes, Zoom uses meeting codes, VS Code tunnels use alphanumeric codes. | LOW | Generate with `secrets.token_hex(3)` (6 chars) or `secrets.token_urlsafe(4)` (6 chars). Store in mount registry. Display prominently in agent CLI output. |
| **Mount landing page** | Browser visitors need a page to enter a mount code or scan a QR. Without this, users have to manually construct URLs. | LOW-MEDIUM | Server-rendered page (Jinja2, matching share link pages pattern) with code input field, QR scanner button, and "Connect" action. Redirects to `/m/{code}/` on submit. |
| **QR code for mount URL** | The existing QR code pattern must extend to remote mounts. Agent CLI should display QR pointing to `relay.example.com/m/{code}`. | LOW | Reuse existing `qr_service.py`. Generate QR with relay URL + mount code. Display in agent terminal output. |
| **Request/response multiplexing** | Multiple browser users hitting the same mount simultaneously. Each HTTP request must be independently correlated with its response over the shared WebSocket tunnel. | MEDIUM | Each request gets a UUID. Agent receives request message, processes it, returns response message with same UUID. Relay holds pending HTTP connections in a dict keyed by UUID, resolves them when response arrives. |
| **Mount disconnect handling** | When the agent goes offline, browser users must see a clear error -- not a hanging spinner or cryptic 502. ngrok shows "Tunnel not found" pages; Cloudflare shows branded error pages. | LOW | Relay returns a clean HTML error page: "This mount is currently offline. The owner may have disconnected." with HTTP 503. Check agent WebSocket liveness before attempting to proxy. |
| **Graceful mount lifecycle** | Mounts have a clear start (agent connects) and end (agent disconnects or TTL expires). The relay must clean up mount registrations promptly. | LOW-MEDIUM | On WebSocket close/error, remove mount from registry immediately. On TTL expiry, send close frame to agent and remove mount. Background task sweeps stale mounts. |
| **Binary data support** | File downloads and uploads are binary. The WebSocket tunnel must handle binary payloads efficiently, not just JSON text frames. | MEDIUM | Use WebSocket binary frames for file content. Protocol: JSON text frame for request/response metadata (headers, status), followed by binary frame(s) for body. Or: encode entire request/response as a binary protocol with header + body segments. |
| **Per-mount password protection** | Reuse v1.1's password protection for individual mounts. The agent specifies `--password` and browser users must enter it. | LOW | The agent's local FastAPI server already has password middleware. Relay proxies the auth flow transparently. Password check happens at the agent, not the relay -- relay is a dumb pipe. |

---

## Differentiators (Competitive Advantage)

Features that elevate this above "just another tunnel."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Full file browser over tunnel** | Unlike ngrok (raw HTTP proxy), this specifically tunnels a rich file management UI with preview, search, clipboard, and drag-drop. The browser experience is identical to LAN mode. No other self-hosted tunnel tool provides a purpose-built file sharing UI. | LOW (already built) | The entire v1.0/v1.1 frontend works unchanged. The relay is transparent -- browser thinks it's talking to a normal web server. The agent runs the full FastAPI app locally. |
| **Mount TTL auto-expire** | Mounts automatically expire after a configurable duration. "Share my folder for 2 hours." Prevents forgotten mounts from staying open indefinitely. ngrok free tier has a 2-hour limit but as a restriction, not a feature. | LOW | Agent sends desired TTL when registering. Relay stores expiry timestamp. Background task closes expired mounts. Agent CLI: `--ttl 2h`. Default: no expiry (explicit stop required). |
| **Mount code + QR dual entry** | Landing page offers both text code entry AND QR scanning. QR is faster for in-person sharing; code is better for text/chat sharing. Most tunnel tools only give you a URL. | LOW | Landing page has both an input field and a QR scanner (using browser camera API or jsQR). Agent CLI prints both the code and QR in terminal. |
| **Existing features over tunnel** | Clipboard sharing, file requests, device discovery -- all existing WebSocket features work through the tunnel because the agent runs the full server. Real-time features that competitors lack entirely. | LOW | WebSocket from browser connects to relay, relay bridges to agent's WebSocket endpoint. Browser-to-agent WebSocket for real-time features is a second tunnel alongside the HTTP proxy tunnel. |
| **Relay status dashboard** | Relay operator sees active mounts, connected agents, request counts, bandwidth. Useful for self-hosted relay deployments. | MEDIUM | Admin endpoint on relay server showing mount registry stats. Protected by admin auth (separate from mount passwords). |
| **Agent reconnection with mount preservation** | If the agent's network blips, reconnect and keep the same mount code. Users don't have to re-share a new code. ngrok-go does this; localtunnel does not. | MEDIUM | Agent stores its mount code and reconnection token. On reconnect, sends token to relay. Relay re-associates the code if it hasn't been reclaimed. Grace period (e.g., 60 seconds) before code is released. |

---

## Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **E2E encryption** | "Relay shouldn't see my files." | Encrypting HTTP request/response payloads at the application layer requires the browser to have a decryption key, which means either a pre-shared key (bad UX) or a key exchange protocol (complex). The relay already uses TLS for transport (HTTPS between browser and relay, WSS between agent and relay), which protects against network sniffing. True E2E requires WebAssembly crypto in the browser -- a v2+ effort. | TLS transport encryption. Relay is trusted infrastructure (self-hosted or operated by the user). Document the trust model. Defer E2E to v2. |
| **WebRTC P2P fallback** | "Skip the relay when possible for direct transfer." | WebRTC requires STUN/TURN servers, ICE negotiation, and browser API integration. Adds massive complexity. Performance gains only matter for large files on fast networks where relay bandwidth is the bottleneck. | Relay-only for v1.2. WebRTC is a separate v2+ milestone. If relay bandwidth is insufficient, users can use LAN mode (v1.0). |
| **Custom domains for mounts** | "I want `files.mydomain.com` instead of a mount code." | Requires DNS configuration (CNAME to relay), TLS certificate provisioning (Let's Encrypt ACME challenge), and subdomain routing. Transforms a simple relay into a full PaaS. | Mount codes are the right UX for temporary file sharing. Custom domains are for permanent tunnels, which is a different product (Cloudflare Tunnel). |
| **Relay-side file caching** | "Cache frequently accessed files on the relay for speed." | Turns the relay from a stateless proxy into a stateful cache. Requires cache invalidation, storage management, consistency checks. Violates "no server storage" constraint in PROJECT.md. | Pure proxy model. Every request goes to the agent. If the agent is slow, that's the agent's problem. |
| **Multi-agent load balancing** | "Multiple agents behind one mount code." | Load balancing file system state across agents creates consistency nightmares. Which agent has the latest file? What about uploads? | One mount = one agent. Period. Multiple mounts can coexist on one relay. |
| **Persistent mounts (survive relay restart)** | "My mount code should survive relay restarts." | Requires persistent storage (database) on the relay. The agent must reconnect anyway after relay restart, so the mount code changes regardless. | Mount codes are ephemeral. Agent reconnects and gets a new code (or same code if reconnection token matches within grace period). Document this behavior. |
| **Server-side rendering on relay** | "Relay should serve the React frontend, not the agent." | If the relay serves the frontend, it needs to know the app's routes, assets, and version. Couples relay to the app. The agent already serves the frontend. | Relay proxies everything including static assets. Browser fetches `index.html` from agent through relay. Relay is app-unaware. |
| **Rate limiting per mount** | "Prevent abuse of individual mounts." | Rate limiting on a relay is complex: per-IP? per-mount? per-agent? Which layer enforces it? The agent already controls its own request handling. | Agent-side rate limiting if needed. The relay can have a global request-per-second cap for infrastructure protection, but per-mount rate limiting is the agent's responsibility. |

---

## Expected Behavior Per Feature

### 1. Agent CLI Mount Command

**How tunnel agents work in the ecosystem:**
- ngrok: `ngrok http 8080` -- connects to ngrok cloud, displays public URL
- cloudflared: `cloudflared tunnel --url http://localhost:8080` -- connects to Cloudflare edge
- localtunnel: `lt --port 8080` -- connects to localtunnel server, displays URL

**Expected behavior for this project:**
- CLI: `wifi-file-server mount ./files --server relay.example.com --password secret --ttl 2h`
- Agent starts a local FastAPI server on a random port (not exposed externally)
- Agent connects to relay via WebSocket: `wss://relay.example.com/agent/connect`
- Agent sends registration message: `{folder_name, password_protected, ttl, read_only, receive}`
- Relay assigns mount code and responds: `{mount_code: "abc123", url: "https://relay.example.com/m/abc123"}`
- Agent displays: mount code, full URL, QR code
- Agent proxies: receives serialized HTTP requests from relay over WebSocket, forwards to local server, returns serialized responses
- Agent handles SIGINT/SIGTERM: sends clean disconnect to relay, shuts down local server

**Complexity: MEDIUM.** New CLI subcommand, WebSocket client (using `websockets` library), request/response serialization, local server lifecycle. ~500-700 LOC.

**Existing code integration points:**
- `cli.py`: New `mount` subcommand (argparse subparsers or separate entry point)
- `config.py`: Reuse `ServerConfig` for the local server
- `main.py`: Reuse `create_app()` to start local server
- New module: `server/app/services/tunnel_client.py` for WebSocket client + request proxy logic

### 2. Relay Server

**How relay servers work in the ecosystem:**
- ngrok: Massive global infrastructure with edge nodes, multiplexing, API gateway
- exposr: Self-hosted, horizontally scalable, WebSocket + SSH transports, Kubernetes-ready
- Community implementations: 100-300 lines of code for basic HTTP-over-WebSocket relay

**Expected behavior for this project:**
- Separate FastAPI application (distinct from the file server)
- Mount registry: in-memory dict mapping mount codes to WebSocket connections
- HTTP routing: requests to `/m/{code}/*` are serialized and sent through the agent's WebSocket
- Agent WebSocket endpoint: `/agent/connect` accepts agent connections, handles registration
- Landing page: `/` shows mount code entry form and QR scanner
- Error pages: mount not found (404), mount offline (503), mount expired (410)
- Health check: `/health` for deployment monitoring
- Admin endpoint (optional): `/admin/mounts` lists active mounts (protected by env var secret)

**Complexity: HIGH.** Separate application with its own routing, WebSocket management, request serialization, connection lifecycle. ~800-1200 LOC for the relay server alone.

**Architecture decisions:**
- Mount codes: 6-character lowercase alphanumeric (`secrets.token_hex(3)`)
- Request serialization: JSON metadata frame + binary body frame per request
- Correlation: UUID per request, stored in pending response dict with asyncio.Future
- Timeout: 30-second timeout per proxied request (returns 504 to browser if agent doesn't respond)
- Concurrency: asyncio handles multiple in-flight requests per mount naturally

### 3. Request/Response Multiplexing Protocol

**How multiplexing works in the ecosystem:**
- ngrok: Custom binary protocol over TCP with stream IDs
- exposr: WebSocket with multiplexed streams
- Community: JSON messages with UUID correlation IDs

**Expected behavior for this project:**

The tunnel protocol multiplexes HTTP requests over a single WebSocket connection:

```
Browser -> Relay: HTTP GET /m/abc123/api/files
Relay -> Agent WS: {id: "uuid-1", type: "http_request", method: "GET", path: "/api/files", headers: {...}}
Agent -> Local Server: HTTP GET http://localhost:PORT/api/files
Local Server -> Agent: HTTP 200 {files: [...]}
Agent -> Relay WS: {id: "uuid-1", type: "http_response", status: 200, headers: {...}}
Agent -> Relay WS: [binary frame: response body bytes, tagged with uuid-1]
Relay -> Browser: HTTP 200 {files: [...]}
```

For large file downloads, the body is streamed in chunks (binary frames with the correlation ID prefix) to avoid buffering entire files in memory.

**Complexity: MEDIUM.** The protocol is straightforward but edge cases (streaming, timeouts, cancellation) add complexity. ~300-400 LOC for the serialization layer.

### 4. WebSocket Reconnection

**How reconnection works in the ecosystem:**
- ngrok-go: Built-in auto-reconnect with configurable heartbeat (10s interval, 10s tolerance)
- websockets library (Python): Default ping every 20s, 20s pong timeout
- Best practice: Exponential backoff with jitter (1s -> 2s -> 4s -> ... -> 30s max)

**Expected behavior for this project:**
- Agent detects disconnect via WebSocket close or missed pong
- Reconnect with exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (cap), with random jitter of 0-1s
- On reconnect, agent sends reconnection token to reclaim its mount code
- Relay holds mount code for 60-second grace period after agent disconnect
- If reconnection succeeds within grace period, mount code is preserved (no URL change for browser users)
- If grace period expires, mount code is released and agent gets a new one
- Agent displays reconnection status in terminal: "Reconnecting (attempt 3/10)..."
- After 10 failed attempts, agent exits with error

**Complexity: LOW-MEDIUM.** Reconnection loop with backoff is ~100 LOC. Grace period on relay is ~50 LOC.

### 5. Mount Landing Page

**How landing pages work in the ecosystem:**
- ngrok: Custom branded error/splash pages for paid plans
- Cloudflare Quick Tunnels: Direct access via URL, no landing page
- Zoom: Meeting code entry page with numeric code field
- VS Code Tunnels: "Authorize this device" page

**Expected behavior for this project:**
- Accessible at relay root: `https://relay.example.com/`
- Clean, minimal design matching the existing share link pages (Jinja2 server-rendered)
- Input field for mount code (6 characters, alphanumeric)
- "Connect" button that navigates to `/m/{code}/`
- QR scan button that opens camera, reads QR, and navigates to the decoded URL
- Recent mounts list (stored in browser localStorage) for quick reconnect
- Error state: "Mount not found" if code is invalid

**Complexity: LOW-MEDIUM.** One Jinja2 template, one form handler, basic JS for QR scanning. ~200-300 LOC.

### 6. Mount TTL Auto-Expire

**How TTL works in the ecosystem:**
- ngrok free: Hard 2-hour limit per session
- Cloudflare Quick Tunnels: No explicit TTL, but "no SLA or uptime guarantee"
- This project v1.1: Share links use `ShareTTL` enum (15min, 1hr, 6hr, 24hr)

**Expected behavior for this project:**
- Agent specifies TTL: `--ttl 2h` (default: no expiry, runs until stopped)
- Agent sends TTL to relay during registration
- Relay stores expiry timestamp per mount
- Background asyncio task checks expiry every 30 seconds
- On expiry: relay sends "mount_expired" message to agent, closes WebSocket, removes mount from registry
- Browser visitors after expiry see: "This mount has expired" (410 Gone)
- Reuse TTL parsing pattern from v1.1 share links

**Complexity: LOW.** TTL storage + background sweep task. ~80-100 LOC.

---

## Feature Dependencies

```
Agent CLI mount command (new subcommand)
    |
    +-- requires --> Relay server (must exist to connect to)
    |
    +-- requires --> Request/response multiplexing protocol (shared between agent + relay)
    |
    +-- reuses --> ServerConfig, create_app(), all file serving infrastructure (v1.0/v1.1)
    |
    +-- reuses --> Password protection middleware (v1.1 -- runs on agent, transparent to relay)
    |
    +-- reuses --> Read-only / receive mode (v1.1 -- runs on agent, transparent to relay)
    |
    +-- reuses --> Share links (v1.1 -- agent-side, token validation local to agent)
    |
    +-- reuses --> QR code generation (v1.0 -- agent displays QR with relay URL)

Relay server (separate application)
    |
    +-- requires --> Request/response multiplexing protocol
    |
    +-- requires --> Mount registry (in-memory dict)
    |
    +-- includes --> Mount landing page (Jinja2 template)
    |
    +-- includes --> Error pages (404, 503, 410)
    |
    +-- includes --> Mount TTL auto-expire (background task)

WebSocket reconnection (agent-side)
    |
    +-- requires --> Agent CLI mount command (reconnection is an enhancement to the base agent)
    |
    +-- requires --> Relay grace period (relay must hold mount code during reconnection window)
```

### Critical Dependency Notes

- **Protocol must be defined first.** Both the agent and relay implement the same serialization protocol. Define it as a shared module or at minimum a shared spec before building either side.
- **Relay is a separate application.** It does NOT share code with the file server (different concerns, different deployment). It MAY share the protocol serialization module.
- **Agent reuses the entire existing app.** The agent starts a local FastAPI server using `create_app()` and proxies to it. All v1.0/v1.1 features work unchanged because the agent IS the file server.
- **Password check happens at the agent, not the relay.** The relay is a dumb pipe. Auth middleware on the agent handles passwords. This means password-protected mounts require the browser to authenticate with the agent through the relay tunnel.
- **WebSocket real-time features need a separate tunnel channel.** Browser WebSocket connections (for clipboard, notifications, device discovery) need to be proxied through the relay to the agent. This is a WebSocket-over-WebSocket tunnel, or the relay can bridge the browser WS to the agent WS.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Risk | Priority |
|---------|------------|---------------------|------|----------|
| Relay server | CRITICAL | HIGH | MEDIUM | P0 |
| Agent CLI mount command | CRITICAL | MEDIUM | MEDIUM | P0 |
| Request/response protocol | CRITICAL | MEDIUM | MEDIUM | P0 |
| Short mount code | HIGH | LOW | LOW | P0 |
| Mount disconnect handling | HIGH | LOW | LOW | P0 |
| Binary data support | HIGH | MEDIUM | MEDIUM | P0 |
| Mount landing page | HIGH | LOW-MEDIUM | LOW | P1 |
| QR code for mount | MEDIUM | LOW | LOW | P1 |
| Per-mount password | MEDIUM | LOW | LOW | P1 |
| Mount TTL auto-expire | MEDIUM | LOW | LOW | P1 |
| WebSocket reconnection | MEDIUM | LOW-MEDIUM | MEDIUM | P1 |
| Agent reconnection with code preservation | MEDIUM | MEDIUM | MEDIUM | P2 |
| Relay status dashboard | LOW | MEDIUM | LOW | P2 |
| Browser WebSocket tunnel (real-time features) | MEDIUM | MEDIUM-HIGH | HIGH | P2 |

**Priority key:**
- **P0: Must ship.** Without these, the feature doesn't exist. Relay + agent + protocol + mount codes + error handling + binary support are the minimum viable tunnel.
- **P1: Should ship.** Landing page, QR, password, TTL, and reconnection make the feature production-quality. Without these it's a demo, not a tool.
- **P2: Can defer.** Code preservation on reconnect, admin dashboard, and full browser WebSocket tunneling are polish. Browser WebSocket tunneling is needed for clipboard/notifications to work over remote mounts -- defer if scope needs to shrink (file browsing/upload/download still works without it).

---

## MVP Definition

### v1.2 Core (Ship Together -- The Tunnel)

- [ ] **Relay server** -- The public-facing proxy. Separate FastAPI app.
- [ ] **Agent CLI mount command** -- `wifi-file-server mount ./files --server relay.example.com`
- [ ] **Request/response multiplexing protocol** -- UUID-correlated HTTP-over-WebSocket.
- [ ] **Short mount code + display** -- 6-char code, printed in terminal with QR.
- [ ] **Mount disconnect handling** -- Clean error pages when agent is offline.
- [ ] **Binary data support** -- File downloads/uploads work through the tunnel.

### v1.2 Full (Ship After Core -- Production Quality)

- [ ] **Mount landing page** -- Code entry + QR scan at relay root.
- [ ] **Per-mount password protection** -- Reuse v1.1 auth, transparent through tunnel.
- [ ] **Mount TTL auto-expire** -- `--ttl 2h` flag on agent.
- [ ] **WebSocket reconnection** -- Auto-reconnect with exponential backoff.
- [ ] **QR code for mount URL** -- Reuse `qr_service.py` with relay URL.

### v1.2 Polish (Ship Last or Defer)

- [ ] **Agent reconnection with mount code preservation** -- Keep same code across reconnects.
- [ ] **Browser WebSocket tunnel** -- Clipboard, notifications, device discovery over remote mount.
- [ ] **Relay status dashboard** -- Admin view of active mounts.

### Defer to v1.3+

- E2E encryption (browser-side crypto)
- WebRTC P2P fallback (skip relay when possible)
- Custom domains for mounts
- Persistent mount codes across relay restarts
- Multi-region relay deployment

---

## Competitor Feature Analysis

| Feature | ngrok | Cloudflare Tunnel | localtunnel | serveo | This Project (v1.2) |
|---------|-------|-------------------|-------------|--------|---------------------|
| Setup complexity | Install agent + sign up | Install cloudflared + sign up | `npx localtunnel` | `ssh` command | `wifi-file-server mount ./files --server URL` |
| Short code access | No (random subdomain URL) | No (random subdomain URL) | No (random subdomain) | No (subdomain) | YES -- 6-char alphanumeric code |
| Purpose-built file UI | No (generic HTTP proxy) | No (generic HTTP proxy) | No (generic HTTP proxy) | No (generic SSH tunnel) | YES -- full file browser with preview, clipboard, requests |
| Password protection | API key (account-level) | Cloudflare Access (separate product) | No | No | Per-mount password via `--password` |
| TTL auto-expire | 2hr limit (free tier restriction) | No | No | No | Configurable TTL via `--ttl` |
| QR code sharing | No | No | No | No | YES -- QR code in terminal + landing page scanner |
| Free tier limits | 1 agent, 20 conns/min | Quick tunnels: 200 concurrent reqs | None (often unreliable) | None (often down) | Self-hosted: no limits |
| Reconnection | Auto with backoff | Auto with HA | No auto-reconnect | No | Auto with exponential backoff + code preservation |
| Self-hostable | No (SaaS only) | No (Cloudflare infra only) | Yes (localtunnel-server) | Yes (single binary) | YES -- relay is a standalone FastAPI app |

**Key insight:** No tunnel tool provides a purpose-built file sharing UI. They all proxy generic HTTP. This project's differentiator is that the tunnel is specifically designed for file sharing with features like short mount codes, QR scanning, password per mount, and TTL. The browser experience is identical to LAN mode -- preview, clipboard, drag-drop, file requests all work.

---

## Sources

- [ngrok agent configuration and heartbeat](https://ngrok.com/docs/agent/config/v3) -- HIGH confidence (official docs)
- [ngrok-go reconnection and resilience](https://deepwiki.com/ngrok/ngrok-go/4.3-reconnection-and-resilience) -- MEDIUM confidence
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/) -- HIGH confidence (official docs)
- [exposr/exposrd](https://github.com/exposr/exposrd) -- MEDIUM confidence (self-hosted relay reference)
- [Building your own Ngrok in 130 lines](https://dev.to/progrium/building-your-own-ngrok-in-130-lines-2lif) -- MEDIUM confidence (architecture reference)
- [Reverse Proxying over WebSockets: Production-Ready Local Tunnel](https://www.codemancers.com/blog/reverse-proxying-over-websockets) -- MEDIUM confidence (multiplexing pattern)
- [How I built Ngrok Alternative](https://dev.to/azimjohn/how-i-built-ngrok-alternative-3n0g) -- MEDIUM confidence (implementation reference)
- [websockets library keepalive docs](https://websockets.readthedocs.io/en/stable/topics/keepalive.html) -- HIGH confidence (official docs)
- [WebSocket reconnection logic best practices](https://oneuptime.com/blog/post/2026-01-27-websocket-reconnection-logic/view) -- MEDIUM confidence
- [awesome-tunneling list](https://github.com/anderspitman/awesome-tunneling) -- MEDIUM confidence (ecosystem survey)
- [localtunnel GitHub](https://github.com/localtunnel/localtunnel) -- MEDIUM confidence
- [root-gg/wsp HTTP tunnel over WebSocket](https://github.com/root-gg/wsp) -- MEDIUM confidence (multiplexing reference)
- Codebase analysis: `server/app/cli.py`, `server/app/config.py`, `server/app/main.py`, `server/app/services/connection_manager.py`, `server/app/middleware/`, `server/app/models/enums.py` -- HIGH confidence

---

*Feature research for: WiFi File Server v1.2 Remote Mounts*
*Researched: 2026-03-11*
