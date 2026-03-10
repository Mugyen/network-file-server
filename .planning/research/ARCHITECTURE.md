# Architecture Research

**Domain:** Remote mount relay server for WiFi file sharing app
**Researched:** 2026-03-11
**Confidence:** HIGH

## System Overview

```
                        INTERNET
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    │   ┌──────────────────────────────────────────────┐       │
    │   │          RELAY SERVER (separate process)     │       │
    │   │                                              │       │
    │   │  ┌────────────┐   ┌───────────────────┐      │       │
    │   │  │ Mount      │   │ HTTP Router       │      │       │
    │   │  │ Registry   │   │ /m/{code}/*       │      │       │
    │   │  │            │   │                   │      │       │
    │   │  │ code->ws   │   │ Extracts code     │      │       │
    │   │  │ mapping    │   │ from URL, proxies │      │       │
    │   │  └─────┬──────┘   │ to agent tunnel   │      │       │
    │   │        │          └────────┬──────────┘      │       │
    │   │        │                   │                 │       │
    │   │  ┌─────┴───────────────────┴──────────┐      │       │
    │   │  │     Tunnel Manager                 │      │       │
    │   │  │                                    │      │       │
    │   │  │  Multiplexes HTTP requests over    │      │       │
    │   │  │  agent WebSocket connections        │      │       │
    │   │  └──────────────┬─────────────────────┘      │       │
    │   │                 │ WebSocket                   │       │
    │   └─────────────────┼────────────────────────────┘       │
    │                     │                                    │
    │   Browser           │              Agent (behind NAT)    │
    │   ┌──────────┐      │              ┌──────────────────┐  │
    │   │ React    │ HTTP │              │ Tunnel Client    │  │
    │   │ SPA      │──────┘              │                  │  │
    │   │          │                     │ WS ──────────────┘  │
    │   │ Served   │                     │ (outbound to relay) │
    │   │ by relay │                     │                     │
    │   └──────────┘                     │ ┌────────────────┐  │
    │                                    │ │ Local FastAPI   │  │
    │                                    │ │ Server          │  │
    │                                    │ │ (reuses         │  │
    │                                    │ │  create_app())  │  │
    │                                    │ └────────────────┘  │
    │                                    └─────────────────────┘
    └──────────────────────────────────────────────────────────┘
```

### Separation Decision: Relay = Separate Process, Agent = New CLI Command

The relay server MUST be a separate FastAPI process (not integrated into the existing LAN server) because:

1. **Deployment target differs.** The relay runs on a cloud VM. The LAN server runs on the user's machine. They have different lifecycles, configs, and network contexts.
2. **No shared state needed.** The relay has its own mount registry; the LAN server has its own file_service config. Merging them creates coupling with zero benefit.
3. **Security boundary.** The relay is internet-facing; the LAN server is LAN-only. Mixing them in one process means the LAN server inherits internet-attack surface.

The agent is a new CLI subcommand (`wifi-file-server mount ...`) that reuses `create_app()` to spin up a local FastAPI server and connects outbound to the relay via WebSocket.

## Component Responsibilities

| Component | Responsibility | New vs Modified |
|-----------|----------------|-----------------|
| **Relay Server** | Accept agent WS connections, route browser HTTP to correct agent, serve landing page + SPA | NEW process |
| **Mount Registry** | Map mount codes to agent WS connections, track TTL/password, generate codes | NEW module in relay |
| **Tunnel Manager** | Multiplex HTTP request/response pairs over a single WS per agent | NEW module in relay |
| **Tunnel Protocol** | Binary framing for request/response over WS (headers + body streaming) | NEW shared module |
| **Agent CLI** | `mount` subcommand: connect to relay, handle tunneled requests using local server | NEW CLI command |
| **Agent Tunnel Client** | Maintain WS to relay, receive framed requests, proxy to local FastAPI, stream responses back | NEW module |
| **Landing Page** | Code entry + QR scan page served by relay at `/` | NEW Jinja2 template |
| **React SPA** | Existing SPA served by relay for `/m/{code}/` routes, API calls prefixed with mount path | MODIFIED (base URL awareness) |
| **file_service.py** | File operations (list, download, upload, etc.) | UNCHANGED (reused by agent's local server) |
| **connection_manager.py** | LAN WebSocket management | UNCHANGED (LAN only) |
| **config.py / ServerConfig** | LAN server config | UNCHANGED |

## Recommended Project Structure

```
server/
├── app/                          # EXISTING - LAN server (unchanged)
│   ├── cli.py                    # MODIFIED - add `mount` subcommand
│   ├── config.py                 # UNCHANGED
│   ├── main.py                   # UNCHANGED
│   ├── routers/                  # UNCHANGED
│   ├── services/
│   │   ├── file_service.py       # UNCHANGED (reused by agent)
│   │   ├── connection_manager.py # UNCHANGED
│   │   └── ...
│   └── middleware/               # UNCHANGED
│
├── relay/                        # NEW - relay server package
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory for relay
│   ├── cli.py                    # `wifi-relay-server` entry point
│   ├── config.py                 # RelayConfig (host, port, max_mounts)
│   ├── registry.py               # MountRegistry: code -> AgentConnection
│   ├── tunnel_manager.py         # Multiplex HTTP over agent WS
│   └── routers/
│       ├── landing.py            # GET / -- code entry page
│       ├── agent_ws.py           # WS /agent/connect -- agent tunnel endpoint
│       └── proxy.py              # /m/{code}/{path:path} -- proxy to agent
│
├── agent/                        # NEW - tunnel agent package
│   ├── __init__.py
│   ├── tunnel_client.py          # WS connection to relay, reconnect logic
│   └── request_handler.py        # Forward tunneled requests to local server
│
└── tunnel/                       # NEW - shared tunnel protocol
    ├── __init__.py
    ├── protocol.py               # Frame types, serialization, constants
    └── frames.py                 # RequestFrame, ResponseFrame, DataChunk

templates/
├── landing.html                  # NEW - mount code entry page
└── ...                           # EXISTING share templates
```

### Structure Rationale

- **`relay/`**: Completely separate FastAPI app. Can be deployed independently. No imports from `app/` except shared tunnel protocol.
- **`agent/`**: Thin orchestration layer. The agent starts a local FastAPI server using `create_app()` and proxies tunneled requests to it. This avoids duplicating any file operation logic.
- **`tunnel/`**: Shared between relay and agent. Defines the wire protocol. No dependencies on either relay or agent internals.
- **`app/` untouched**: The existing LAN server sees zero changes except `cli.py` gaining a `mount` subcommand that imports from `agent/`.

## Architectural Patterns

### Pattern 1: Request-Response Multiplexing Over Single WebSocket

**What:** Each agent maintains ONE WebSocket to the relay. Multiple concurrent browser requests for that mount are multiplexed over this single connection using request IDs.

**When to use:** Always. One WS per agent is simpler than connection pooling and avoids NAT/firewall issues with multiple outbound connections.

**Trade-offs:** Simpler connection management, but requires careful framing. Head-of-line blocking is possible if one large file transfer saturates the WS. Mitigation: chunk data frames into 64KB to allow interleaving of concurrent requests.

**Protocol design:**

```python
from enum import IntEnum
import struct
from dataclasses import dataclass


class FrameType(IntEnum):
    """Types of frames in the tunnel protocol."""
    REQUEST_HEADER = 0x01    # Relay -> Agent: HTTP request metadata
    REQUEST_BODY = 0x02      # Relay -> Agent: request body chunk
    REQUEST_END = 0x03       # Relay -> Agent: request body complete
    RESPONSE_HEADER = 0x04   # Agent -> Relay: HTTP response metadata
    RESPONSE_BODY = 0x05     # Agent -> Relay: response body chunk
    RESPONSE_END = 0x06      # Agent -> Relay: response complete
    HEARTBEAT = 0x07         # Bidirectional keepalive
    ERROR = 0x08             # Either direction: request-level error


# Wire format: [type:1][request_id:4][payload_len:4][payload:N]
# Total header: 9 bytes. Max payload: 64KB per frame (for interleaving).
FRAME_HEADER_SIZE = 9
MAX_PAYLOAD_SIZE = 65536  # 64KB chunks for file streaming


@dataclass(frozen=True)
class TunnelFrame:
    """Single frame in the tunnel protocol."""
    frame_type: FrameType
    request_id: int       # uint32, unique per request within a session
    payload: bytes

    def serialize(self) -> bytes:
        header = struct.pack(
            "!BII",
            self.frame_type,
            self.request_id,
            len(self.payload),
        )
        return header + self.payload

    @staticmethod
    def deserialize(data: bytes) -> "TunnelFrame":
        frame_type, request_id, payload_len = struct.unpack(
            "!BII", data[:FRAME_HEADER_SIZE]
        )
        payload = data[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len]
        return TunnelFrame(
            frame_type=FrameType(frame_type),
            request_id=request_id,
            payload=payload,
        )
```

### Pattern 2: Reverse Tunnel (Agent Connects Outbound)

**What:** The agent initiates the WebSocket connection to the relay (outbound). The relay never connects to the agent. This is the ngrok/localtunnel pattern.

**When to use:** Always for this use case. Users behind NAT/firewalls cannot accept inbound connections.

**Trade-offs:** Agent must handle reconnection (relay restarts, network flaps). Relay cannot "push" to an agent that hasn't connected yet.

**Connection lifecycle:**

```
Agent                           Relay
  |                               |
  |-- WS CONNECT /agent/connect ->|
  |   (with mount_code, password, |
  |    ttl in query params)       |
  |                               |
  |<- ACCEPT + mount registered --|
  |                               |
  |<-- HEARTBEAT (every 30s) ---->|  (bidirectional)
  |                               |
  |<-- REQUEST_HEADER (req #1) ---|  (browser request arrives)
  |                               |
  |--- RESPONSE_HEADER (req #1)->-|
  |--- RESPONSE_BODY (req #1) -->|
  |--- RESPONSE_END (req #1) --->|
  |                               |
  |<-- WS CLOSE ------------------|  (TTL expired / agent disconnect)
```

### Pattern 3: URL-Based Mount Routing

**What:** Browser requests to `/m/{code}/api/files` are routed to the agent registered under `{code}`. The relay strips the `/m/{code}` prefix before forwarding to the agent, so the agent sees `/api/files` -- identical to LAN server paths.

**When to use:** This is the only routing strategy that works with the existing React SPA without rewriting API calls.

**Trade-offs:** The SPA needs to know its base URL (`/m/{code}`) so it prefixes API calls correctly. This is a small change: inject `window.__MOUNT_BASE__` via the HTML template or use a relative URL strategy.

**Relay-side implementation:**

```python
# relay/routers/proxy.py
@router.api_route(
    "/m/{code}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def proxy_to_agent(
    code: str, path: str, request: Request,
) -> StreamingResponse:
    registry = get_mount_registry()
    agent_conn = registry.get_agent(code)  # Raises MountNotFoundError

    # Build tunneled request (strip /m/{code} prefix)
    request_id = agent_conn.next_request_id()
    header_frame = build_request_header_frame(
        request_id=request_id,
        method=request.method,
        path=f"/{path}",
        headers=dict(request.headers),
        query=str(request.query_params),
    )

    # Send request through tunnel, stream response back
    response_queue = agent_conn.create_response_queue(request_id)
    await agent_conn.send_frame(header_frame)

    # Stream request body if present
    async for chunk in request.stream():
        body_frame = TunnelFrame(FrameType.REQUEST_BODY, request_id, chunk)
        await agent_conn.send_frame(body_frame)
    await agent_conn.send_frame(
        TunnelFrame(FrameType.REQUEST_END, request_id, b"")
    )

    # Wait for response header
    resp_header = await response_queue.get_header()

    return StreamingResponse(
        response_queue.body_iterator(),
        status_code=resp_header.status_code,
        headers=resp_header.headers,
    )
```

### Pattern 4: Agent Proxies to Local FastAPI Server

**What:** The agent starts a local FastAPI server using the SAME `create_app()` factory on a random port. Tunneled requests are forwarded to this local server via `httpx`. The local server handles all file operations identically to LAN mode.

**When to use:** Always. This is the simplest approach that guarantees behavior parity between LAN and remote modes.

**Trade-offs:** Slight overhead of localhost HTTP roundtrip (negligible -- sub-millisecond). Massive simplification: the agent does not need to reimplement response formatting, content negotiation, FileResponse, StreamingResponse, middleware, or any routing logic.

```python
# agent/request_handler.py
import httpx


class AgentRequestHandler:
    """Forwards tunneled requests to the local FastAPI server."""

    def __init__(self, local_port: int) -> None:
        self._base_url = f"http://127.0.0.1:{local_port}"
        self._client = httpx.AsyncClient(base_url=self._base_url)

    async def handle_request(
        self,
        request_id: int,
        method: str,
        path: str,
        headers: dict[str, str],
        query: str,
        body_chunks: list[bytes],
    ) -> AsyncIterator[TunnelFrame]:
        """Forward request to local server, yield response frames."""
        url = path
        if query:
            url = f"{path}?{query}"

        # Remove hop-by-hop headers
        filtered_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in ("host", "transfer-encoding", "connection")
        }

        body = b"".join(body_chunks) if body_chunks else None

        response = await self._client.request(
            method=method,
            url=url,
            headers=filtered_headers,
            content=body,
        )

        # Yield response header frame
        yield build_response_header_frame(
            request_id, response.status_code, dict(response.headers),
        )

        # Yield body in 64KB chunks
        offset = 0
        while offset < len(response.content):
            chunk = response.content[offset:offset + MAX_PAYLOAD_SIZE]
            yield TunnelFrame(FrameType.RESPONSE_BODY, request_id, chunk)
            offset += MAX_PAYLOAD_SIZE

        yield TunnelFrame(FrameType.RESPONSE_END, request_id, b"")

    async def close(self) -> None:
        await self._client.aclose()
```

**Streaming improvement for v1.2+:** The above buffers the full response. For large file downloads, use `httpx` streaming mode:

```python
async with self._client.stream(method, url, headers=filtered_headers) as response:
    yield build_response_header_frame(request_id, response.status_code, dict(response.headers))
    async for chunk in response.aiter_bytes(chunk_size=MAX_PAYLOAD_SIZE):
        yield TunnelFrame(FrameType.RESPONSE_BODY, request_id, chunk)
    yield TunnelFrame(FrameType.RESPONSE_END, request_id, b"")
```

This is the recommended approach -- it streams files through the tunnel without buffering.

## Data Flow

### Browser Request Through Tunnel

```
Browser (GET /m/abc123/api/files?path=docs)
    |
    v
Relay HTTP Router
    | strips /m/abc123, looks up agent for "abc123"
    v
Tunnel Manager
    | assigns request_id=42, serializes to binary frames
    v
Agent WebSocket (binary frames over WS)
    | REQUEST_HEADER(42, "GET /api/files?path=docs", headers)
    v
Agent Tunnel Client
    | deserializes frame, forwards to local FastAPI via httpx
    v
Local FastAPI (127.0.0.1:random_port)
    | file_service.list_directory(shared_folder, "docs")
    v
Agent Tunnel Client
    | reads httpx response, serializes to binary frames
    | RESPONSE_HEADER(42, 200, headers)
    | RESPONSE_BODY(42, json_bytes)
    | RESPONSE_END(42)
    v
Relay Tunnel Manager
    | reassembles response for request_id=42
    v
Browser receives JSON response
```

### File Download Through Tunnel (Streaming)

```
Browser (GET /m/abc123/api/files/download?path=video.mp4)
    |
    v
Relay: creates request_id=99, sends REQUEST_HEADER to agent
    |
    v
Agent: httpx streams from local server (FileResponse)
Agent: streams file in 64KB RESPONSE_BODY frames
    | RESPONSE_HEADER(99, 200, {"content-type": "video/mp4", ...})
    | RESPONSE_BODY(99, <64KB chunk>)
    | RESPONSE_BODY(99, <64KB chunk>)
    | ...
    | RESPONSE_END(99)
    v
Relay: StreamingResponse yields chunks as they arrive from WS
    v
Browser: downloads file progressively
```

### Mount Registration Flow

```
Agent CLI: wifi-file-server mount ./photos --relay wss://relay.example.com
    |
    | 1. Start local FastAPI on random port (using create_app())
    | 2. Set ServerConfig for the local server
    | 3. Generate or accept mount code
    | 4. Connect WS to relay
    v
Relay /agent/connect?code=abc123&ttl=3600
    |
    | 5. Validate code uniqueness
    | 6. Register in MountRegistry {code -> ws}
    | 7. Start TTL countdown (asyncio.Task with sleep)
    | 8. Accept WS
    v
Agent: print "Mounted at https://relay.example.com/m/abc123"
Agent: print QR code for the mount URL
```

### Key Data Flows

1. **Mount registration:** Agent connects outbound, relay registers code in memory. No persistence needed -- mounts are ephemeral by design, matching the share links pattern from v1.1.
2. **Request proxying:** Relay receives browser HTTP, serializes to binary WS frames, agent deserializes and proxies to local server, response flows back.
3. **File streaming:** Large files are chunked into 64KB frames. Relay yields chunks to browser as StreamingResponse as they arrive -- no buffering the full file on relay.
4. **Heartbeat:** Bidirectional ping every 30 seconds. Three missed heartbeats = connection dead, mount deregistered.
5. **TTL expiry:** Relay asyncio.Task sleeps for TTL duration, then closes agent WS and removes mount from registry. Agent detects close and exits cleanly.

## Integration Points

### With Existing Codebase

| Integration Point | What Changes | Risk |
|-------------------|-------------|------|
| `cli.py` | Add `mount` subcommand via argparse subparsers | LOW -- additive, existing `serve` behavior becomes default subcommand |
| `create_app()` | Nothing -- agent calls it as-is to start local server | NONE |
| `file_service.py` | Nothing -- reused as-is by agent's local FastAPI | NONE |
| `config.py` | Nothing -- agent creates its own `ServerConfig` | NONE |
| React SPA | Must support configurable API base URL | MEDIUM -- need to audit all `fetch()` calls in `client/src/api/` |
| `connection_manager.py` | Nothing -- LAN-only, not used by relay | NONE |
| `pyproject.toml` | Add httpx + websockets dependencies, add relay entry point | LOW |
| SPA build (vite) | Relay serves the same `client/dist` build output | NONE -- no build changes needed |

### New External Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `httpx` | Agent's async HTTP client to local server | Mature, async-native, streaming support. Already widely used in FastAPI ecosystem. |
| `websockets` | Agent's WS client to relay | FastAPI/Starlette WS is server-side only; agent needs a client library. `websockets` is the standard Python async WS client. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Relay <-> Agent | WebSocket (binary frames) | Custom tunnel protocol defined in `tunnel/` |
| Agent <-> Local Server | HTTP (localhost) | Standard FastAPI request/response via httpx |
| Browser <-> Relay | HTTP + (optionally WS) | Standard web, relay serves SPA static files |
| Relay landing <-> SPA | HTTP redirect | `/m/{code}/` serves the SPA with injected base URL |

## SPA Base URL Strategy

The React SPA currently makes API calls to hardcoded paths (`/api/files`, `/ws`). When served through the relay at `/m/{code}/`, these calls must target `/m/{code}/api/files` instead.

**Recommended approach:** The relay serves the SPA's `index.html` with an injected `<script>` tag:

```html
<script>window.__MOUNT_BASE__ = "/m/abc123";</script>
```

The SPA reads `window.__MOUNT_BASE__` (defaulting to `""` for LAN mode) and prefixes all API/WS URLs. This requires:

1. A `getBaseUrl()` function in `client/src/api/` that returns `window.__MOUNT_BASE__ || ""`
2. All `fetch()` calls in 5-6 API files prefixed with `getBaseUrl()`
3. The WebSocket hook uses the base URL for its WS endpoint
4. Zero changes to React components -- only the API layer changes

This is the lowest-risk approach because:
- LAN mode is completely unaffected (base is `""`)
- No React Router needed (the SPA is a single page, no client-side routing)
- The relay controls the injected value per mount code

### WebSocket in Remote Mode

The existing SPA WebSocket (`/ws`) provides clipboard sync, device notifications, file requests, and device discovery. In remote mode:

**Recommendation for v1.2:** Disable real-time WS features in remote mode. The remote SPA does not connect to the LAN server's WS. Remote users only need file browsing and downloading. Clipboard sync and device discovery are LAN-context features that make no sense over a relay tunnel.

The SPA already gracefully handles WS unavailability -- it shows a "reconnecting" banner via `ConnectionStatus`. In remote mode, the SPA detects `window.__MOUNT_BASE__` is set and skips the WS connection entirely. The banner is hidden since WS is intentionally disabled, not failing.

### Password Protection in Remote Mode

The existing cookie-based auth middleware works through the tunnel because:
1. Browser sends HTTP to relay, relay forwards to agent, agent's local server has auth middleware
2. Cookies are set on the relay domain (the browser's perspective), not localhost
3. The relay transparently proxies Set-Cookie headers from agent responses

The agent's `mount` subcommand accepts `--password` the same way `serve` does. If set, the local FastAPI server has auth middleware. Browser must log in through the relay before accessing files.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-50 mounts | Single relay process, in-memory registry. This is the v1.2 target. |
| 50-500 mounts | Still single process. Python async handles this -- each mount is just a WS connection + request forwarding. Bottleneck is bandwidth, not connections. |
| 500+ mounts | Redis-backed registry for multi-process relay. Sticky sessions or WS connection pinning. Out of scope for v1.2. |

### Scaling Priorities

1. **First bottleneck:** Bandwidth per relay instance. Large file downloads through the relay consume relay egress. No mitigation in v1.2 -- this is inherent to the relay model. Future: WebRTC P2P fallback (already planned for v2+).
2. **Second bottleneck:** Head-of-line blocking when multiple large downloads happen concurrently over a single agent WS. 64KB chunking with interleaving mitigates this, but sustained throughput will be lower than direct LAN. Acceptable tradeoff.

## Anti-Patterns

### Anti-Pattern 1: Buffering Full Responses on Relay

**What people do:** Read the entire agent response into memory before sending to browser.
**Why it's wrong:** A 2GB video file would OOM the relay server.
**Do this instead:** Stream response body frames directly to the browser StreamingResponse as they arrive over WS. Use an `asyncio.Queue` per request_id: agent pushes frames, relay pops and yields.

### Anti-Pattern 2: Using JSON for Tunnel Protocol

**What people do:** JSON-encode every request/response including binary file data (base64).
**Why it's wrong:** Base64 inflates data by 33%. JSON parsing is slow for high-throughput file transfers. Cannot efficiently stream.
**Do this instead:** Use binary WebSocket frames with a compact binary header (9 bytes: type + request_id + length). Payload is raw bytes.

### Anti-Pattern 3: One WebSocket Per Browser Request

**What people do:** Agent opens a new WS connection for each incoming browser request (the ngrok "on-demand tunnel" pattern).
**Why it's wrong:** Connection setup latency (WS handshake) adds 100-300ms per request. Firewall/NAT may rate-limit new connections.
**Do this instead:** Multiplex all requests over the single persistent agent WS. Use request IDs to demultiplex.

### Anti-Pattern 4: Merging Relay Into LAN Server

**What people do:** Add relay routes to the existing FastAPI app and deploy "one server does everything."
**Why it's wrong:** LAN server is private, relay is public. Different security models, deployment targets, and lifecycles. Users running LAN mode should not expose relay endpoints.
**Do this instead:** Separate processes. Shared code (tunnel protocol) lives in shared packages.

### Anti-Pattern 5: Agent Re-implements File Operations

**What people do:** Write a parallel set of file listing/download/upload handlers in the agent instead of reusing the existing server.
**Why it's wrong:** Code duplication. Bugs fixed in `file_service.py` won't be fixed in agent's copy. Behavior divergence between LAN and remote modes.
**Do this instead:** Agent starts a local FastAPI server using the SAME `create_app()` factory and proxies tunneled requests to it via localhost HTTP using httpx.

### Anti-Pattern 6: Subdomain-Based Routing

**What people do:** Route mounts via subdomains (`abc123.relay.example.com`) like ngrok does.
**Why it's wrong:** Requires wildcard DNS, wildcard TLS certificates, and DNS propagation time. Massively increases deployment complexity for a simple file sharing tool.
**Do this instead:** Path-based routing (`relay.example.com/m/abc123/`). Works with a single domain, single TLS cert, zero DNS complexity.

## Build Order (Dependency-Driven)

This ordering is based on strict dependency analysis. Each step can be tested in isolation before proceeding.

| Order | Component | Depends On | Can Test Without |
|-------|-----------|------------|------------------|
| 1 | Tunnel Protocol (`server/tunnel/`) | Nothing | Everything -- pure data structures |
| 2 | Mount Registry (`server/relay/registry.py`) | Nothing | Everything -- in-memory dict with TTL |
| 3 | Relay Server skeleton + landing page | #2 | Agents -- can verify landing page renders |
| 4 | Agent `mount` subcommand + local server | Existing `create_app()` | Relay -- can verify local server starts |
| 5 | Agent tunnel client (WS to relay) | #1, #4 | Browser proxy -- can verify WS connects |
| 6 | Relay agent WS endpoint + tunnel manager | #1, #2, #3 | Browser -- can verify agent registers |
| 7 | Relay proxy router (`/m/{code}/*`) | #1, #6 | Nothing -- full E2E works |
| 8 | SPA base URL support | #7 | Nothing -- this is the UI polish |
| 9 | Password + TTL for mounts | #7 | Nothing -- reuses existing auth patterns |

**Rationale:**
- Tunnel protocol first because it is a pure shared library with no dependencies. Unit-testable with pytest alone.
- Registry before relay because the relay needs it, but registry needs nothing.
- Agent local server before tunnel client because we want to verify `create_app()` works in agent context before adding WS complexity.
- Proxy router last among core components because it requires both relay and agent to be functional.
- SPA changes deferred until proxy works so we can test with curl/httpie first.
- Auth/TTL last because they are additive features on a working tunnel.

## Sources

- [IETF WebSocket Multiplexing Draft](https://datatracker.ietf.org/doc/html/draft-ietf-hybi-websocket-multiplexing-01) -- multiplexing extension design for WS channel IDs
- [wsrtunnel - Python Reverse HTTP Tunnel](https://github.com/defreng/wsrtunnel) -- reference implementation of WS-based reverse HTTP tunnel
- [wstunnel - Tunnel over WebSocket](https://github.com/erebe/wstunnel) -- production WS tunnel with binary framing
- [awesome-tunneling](https://github.com/anderspitman/awesome-tunneling) -- comprehensive list of tunnel architectures
- [FastAPI WebSocket docs](https://fastapi.tiangolo.com/advanced/websockets/) -- binary data handling with receive_bytes/send_bytes
- [WebSocket binary framing](https://www.appetenza.com/websocket-handling-binary-data) -- binary data handling patterns
- Existing codebase: `server/app/main.py`, `server/app/services/connection_manager.py`, `server/app/routers/websocket.py`, `server/app/services/file_service.py`, `server/app/cli.py`, `server/app/config.py`

---
*Architecture research for: Remote mount relay server integration with existing WiFi file sharing app*
*Researched: 2026-03-11*
