# Project Research Summary

**Project:** WiFi File Server v1.2 Remote Mounts
**Domain:** WebSocket tunnel relay + agent CLI for internet-accessible file sharing
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

v1.2 adds internet-accessible file sharing to the existing LAN-only WiFi File Server. The proven architecture for this is a reverse tunnel: an agent CLI on the user's machine connects outbound to a public relay server via WebSocket, and the relay proxies browser HTTP requests through the tunnel to the agent. This is the same pattern used by ngrok, Cloudflare Tunnel, and localtunnel. The differentiator is that this project tunnels a purpose-built file sharing UI (preview, clipboard, drag-drop) rather than generic HTTP, and uses short mount codes instead of random subdomains.

The recommended approach requires only one new production dependency (`websockets>=16.0` for the agent's outbound WebSocket client). Everything else -- FastAPI, Starlette WebSocket, argparse, aiofiles, itsdangerous, Jinja2 -- is already in the stack and reused directly. The relay server is a separate FastAPI application (different process, different deployment target) that maintains an in-memory mount registry. The agent reuses the existing `create_app()` factory to start a local FastAPI server and proxies tunneled requests to it via httpx, guaranteeing behavior parity between LAN and remote modes with zero code duplication.

The critical risks are: (1) relay OOM from unbounded buffering during large file transfers -- solved by chunk-level backpressure using `asyncio.Queue(maxsize=N)`, (2) request-response correlation failure under concurrent access -- solved by UUID-tagged binary frames in the tunnel protocol, and (3) mount code brute force on the internet-facing relay -- solved by rate limiting and optional per-mount passwords. The tunnel protocol design (binary framing, correlation IDs, backpressure) is the single highest-risk component. Getting it wrong requires a rewrite; getting it right makes everything else straightforward.

## Key Findings

### Recommended Stack

The existing stack covers nearly everything. The only new production dependency is `websockets>=16.0` for the agent's outbound WebSocket client connection. The relay uses FastAPI/Starlette's built-in WebSocket support (server-side). The tunnel wire protocol is custom: binary WebSocket frames with a 9-byte header (type, request_id, payload_length) for file data, and JSON text frames for control messages. No msgpack, protobuf, or RPC libraries needed.

**Core technologies (new):**
- `websockets>=16.0`: Agent WebSocket client -- the standard Python async WS client, lightweight, likely already installed via uvicorn

**Core technologies (reused, unchanged):**
- FastAPI/Starlette WebSocket: Relay accepts agent and browser connections via `@app.websocket()`
- `httpx`: Agent proxies tunneled requests to its local FastAPI server (already in dev deps, move to production)
- `itsdangerous`: Mount code generation with TTL expiry (reuses share link pattern from v1.1)
- `argparse` subcommands: New `mount` and `relay` subcommands alongside existing `serve`
- `aiofiles`: Agent reads local files asynchronously for streaming through tunnel
- Jinja2: Mount landing page (code entry + QR scan)

### Expected Features

**Must have (table stakes -- P0):**
- Relay server with mount routing (`/m/{code}/*` proxied to agent)
- Agent CLI mount command (`wifi-file-server mount ./files --server relay.example.com`)
- Request/response multiplexing protocol with UUID correlation
- Short mount code (6-char alphanumeric) displayed with QR
- Mount disconnect handling (clean error pages: offline, expired, not found)
- Binary data support (file downloads/uploads work through tunnel)

**Should have (production quality -- P1):**
- Mount landing page with code entry and QR scanner
- Per-mount password protection (reuses v1.1 auth, transparent through tunnel)
- Mount TTL auto-expire (`--ttl 2h`)
- WebSocket reconnection with exponential backoff + jitter
- QR code for mount URL in agent terminal

**Defer (v1.2 polish or later):**
- Agent reconnection with mount code preservation (P2)
- Browser WebSocket tunnel for clipboard/notifications (P2 -- file browsing works without it)
- Relay admin status dashboard (P2)
- E2E encryption, WebRTC P2P, custom domains, persistent mounts (v1.3+)

### Architecture Approach

The system has three distinct components: relay server (separate FastAPI app on cloud VM), agent CLI (new subcommand reusing existing app), and shared tunnel protocol (binary framing library). The relay is a stateless proxy with an in-memory mount registry. The agent starts a local FastAPI server using `create_app()` and forwards tunneled requests to it via localhost httpx, which guarantees all v1.0/v1.1 features work identically in remote mode without any code duplication.

**Major components:**
1. **Relay Server** (`server/relay/`) -- Separate FastAPI app: accepts agent WS connections, routes browser HTTP by mount code, serves landing page
2. **Agent CLI** (`server/agent/`) -- New `mount` subcommand: connects outbound to relay, proxies tunneled requests to local FastAPI server
3. **Tunnel Protocol** (`server/tunnel/`) -- Shared binary framing: 9-byte header + payload, binary frames for file data, JSON for control
4. **Mount Registry** (`server/relay/registry.py`) -- In-memory `dict[str, WebSocket]` mapping codes to agent connections with TTL tracking
5. **SPA Base URL** -- Inject `window.__MOUNT_BASE__` so React SPA prefixes API calls with `/m/{code}` in remote mode

### Critical Pitfalls

1. **Relay OOM from unbounded buffering** -- Use `asyncio.Queue(maxsize=4)` between WS receiver and HTTP response writer. Stream 64KB chunks; never buffer full files. This is the highest-recovery-cost pitfall -- cannot be patched onto a buffering design.
2. **Request-response correlation failure** -- Every frame (including every body chunk) must carry the request ID. Use `dict[int, asyncio.Future]` on relay with 30-second timeouts. Wrong correlation silently delivers wrong file content.
3. **Mount code brute force** -- 6+ character codes, rate limit to 5 failures/IP/minute, support per-mount passwords. Default mount mode must be read-only (`--allow-upload` for writes).
4. **Agent reconnection drops in-flight requests** -- On disconnect, immediately fail all pending Futures with 503. On reconnect, atomically swap WS reference. Never allow two tunnels for same mount.
5. **LAN mode regression** -- Agent code must be isolated: lazy imports, separate CLI subcommand, zero changes to existing modules. Existing test suite must pass unmodified.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Tunnel Protocol and Project Structure

**Rationale:** The tunnel protocol is the foundation that both relay and agent depend on. It is also the highest-risk component (binary framing, correlation IDs, backpressure). Defining it first allows independent development of relay and agent. Project structure (module boundaries) must be established to avoid LAN mode regression.
**Delivers:** Shared `server/tunnel/` package with frame types, serialization, constants. CLI restructured to argparse subcommands. Module boundaries established.
**Addresses:** Binary data support (P0), request/response multiplexing (P0)
**Avoids:** Pitfall 2 (correlation failure), Pitfall 5 (open proxy), Pitfall 6 (LAN regression), Pitfall 8 (JSON encoding)

### Phase 2: Relay Server Core

**Rationale:** The relay must exist before the agent can connect to it. It is the highest-complexity component (~800-1200 LOC). Building it second allows using the tunnel protocol from Phase 1.
**Delivers:** Separate FastAPI app with mount registry, agent WS endpoint, HTTP proxy router, error pages, health check. Rate limiting on mount code lookups.
**Addresses:** Relay server (P0), mount disconnect handling (P0), short mount code (P0)
**Avoids:** Pitfall 1 (OOM -- backpressure in proxy), Pitfall 4 (brute force -- rate limiting)

### Phase 3: Agent CLI and Tunnel Client

**Rationale:** Agent connects to the relay from Phase 2. Reuses `create_app()` for local server and httpx for proxying. Lower risk than relay because it mostly glues existing components together.
**Delivers:** `wifi-file-server mount ./files --server URL` command, WebSocket client to relay, request handler proxying to local FastAPI, QR code display.
**Addresses:** Agent CLI mount command (P0), QR code (P1)
**Avoids:** Pitfall 5 (agent re-validates all paths), Pitfall 6 (lazy imports, separate subcommand)

### Phase 4: Production Hardening

**Rationale:** Core tunnel works from Phases 1-3. This phase adds the features that make it production-quality rather than a demo.
**Delivers:** Mount landing page, per-mount password, TTL auto-expire, WebSocket reconnection with backoff, SPA base URL injection.
**Addresses:** Landing page (P1), password (P1), TTL (P1), reconnection (P1)
**Avoids:** Pitfall 3 (reconnection drops requests -- fail Futures on disconnect), Pitfall 7 (TTL kills active downloads -- grace period)

### Phase 5: Polish and Advanced Features

**Rationale:** Everything works and is hardened. This phase adds nice-to-haves that can be deferred if scope needs to shrink.
**Delivers:** Mount code preservation across reconnects, browser WebSocket tunnel for real-time features, relay admin dashboard.
**Addresses:** P2 features (code preservation, WS tunnel, dashboard)

### Phase Ordering Rationale

- Protocol first because it is a pure library with no dependencies, unit-testable in isolation, and required by both relay and agent. Getting binary framing + correlation right prevents the highest-cost pitfalls.
- Relay before agent because the agent needs a relay to connect to. The relay can be tested with mock WebSocket clients before the agent exists.
- Agent after relay because the agent is simpler (glues existing components) and can immediately be tested end-to-end against the relay.
- Hardening after core because password, TTL, reconnection, and landing page are additive features on a working tunnel. They do not change the protocol.
- Polish last because P2 features (code preservation, WS tunnel, dashboard) have diminishing returns and can be cut without affecting core functionality.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Tunnel Protocol):** Binary framing design, backpressure strategy, and streaming semantics need careful specification. The ARCHITECTURE.md provides concrete protocol code but edge cases (partial frames, connection drops mid-frame) need validation.
- **Phase 4 (Production Hardening):** Needs audit of all `fetch()` calls in `client/src/api/` to confirm `window.__MOUNT_BASE__` prefix approach works. Cookie behavior through relay proxy needs validation (Set-Cookie domain/path rewriting).

Phases with standard patterns (skip research-phase):
- **Phase 2 (Relay Server):** Well-documented FastAPI WebSocket patterns. Mount registry is a simple in-memory dict. Proxy router is standard catch-all route.
- **Phase 3 (Agent CLI):** Straightforward argparse subcommand + websockets client library. Proxying via httpx to localhost is a standard pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only one new dependency. All alternatives evaluated and rejected with clear rationale. websockets 16.0 verified on PyPI. |
| Features | HIGH | Verified against ngrok, Cloudflare Tunnel, localtunnel, exposr, and community implementations. Feature prioritization matrix well-justified. |
| Architecture | HIGH | Binary tunnel protocol with concrete code samples. Build order is dependency-driven and testable at each step. Agent-reuses-create_app pattern eliminates duplication risk. |
| Pitfalls | HIGH | Based on codebase analysis of existing WS/auth infra plus verified external patterns. Recovery costs accurately assessed. |

**Overall confidence:** HIGH

### Gaps to Address

- **SPA base URL injection:** No research validated that all existing fetch() calls can be cleanly prefixed. Needs a code audit of `client/src/api/` during Phase 4 planning.
- **Browser WebSocket tunneling:** Deferred to P2 but the approach (WS-over-WS bridging vs relay-level fan-out) is not fully specified. Needs research if Phase 5 is pursued.
- **Relay deployment:** No research on specific cloud deployment (Docker, systemd, reverse proxy config). Straightforward but undocumented.
- **httpx as production dependency:** Currently in dev deps only. Moving to production deps is trivial but needs explicit pyproject.toml change.
- **Cookie behavior through relay proxy:** Research claims cookies work transparently, but Set-Cookie domain/path attributes may need relay-side rewriting. Needs validation during Phase 4.

## Sources

### Primary (HIGH confidence)
- [websockets 16.0 docs](https://websockets.readthedocs.io/en/stable/) -- async client API, ping/pong, memory management
- [FastAPI WebSocket reference](https://fastapi.tiangolo.com/reference/websockets/) -- send_bytes/receive_bytes, connection lifecycle
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html) -- origin validation, auth, rate limiting
- Codebase analysis: `server/app/cli.py`, `server/app/config.py`, `server/app/main.py`, `server/app/services/file_service.py`, `server/app/middleware/`

### Secondary (MEDIUM confidence)
- [wsrtunnel](https://github.com/defreng/wsrtunnel), [wstunnel](https://github.com/erebe/wstunnel), [root-gg/wsp](https://github.com/root-gg/wsp) -- reference tunnel implementations
- [exposr/exposrd](https://github.com/exposr/exposrd) -- self-hosted relay architecture reference
- [awesome-tunneling](https://github.com/anderspitman/awesome-tunneling) -- ecosystem survey
- Community articles on building ngrok alternatives -- architecture validation

### Tertiary (LOW confidence)
- WebSocket backpressure patterns from blog posts -- principles verified but specific asyncio.Queue sizing needs load testing

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
