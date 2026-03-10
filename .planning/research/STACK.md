# Stack Research: v1.2 Remote Mounts

**Domain:** WebSocket tunnel relay + agent CLI for remote file sharing
**Researched:** 2026-03-11
**Confidence:** HIGH

## Guiding Principle: Zero New Dependencies Where Possible

The existing stack (FastAPI + Starlette WebSocket + argparse + asyncio) already provides every primitive needed for the relay server and agent CLI. The tunnel is a custom protocol over WebSocket -- no off-the-shelf library solves this exact problem, so we build it with what we have. The only new dependency is `websockets` for the agent's outbound WebSocket client connection.

## Recommended Stack Additions

### Core Technologies (NEW)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `websockets` | `>=16.0` | Agent-side WebSocket client connecting outbound to relay | The standard Python WebSocket client library. FastAPI/Starlette only provides server-side WebSocket -- the agent needs a client. `websockets` 16.0 supports asyncio natively, handles ping/pong keepalive, binary frames, and reconnection. Already battle-tested, pure Python, no C extensions needed. uvicorn already uses it internally so it is likely already installed. |

### Existing Technologies (REUSED -- no version changes)

| Technology | Already In Stack | Reuse For |
|------------|-----------------|-----------|
| FastAPI WebSocket (`starlette.websockets`) | `fastapi>=0.115.0` | Relay server accepts agent tunnel connections and browser WebSocket connections via `@app.websocket()` endpoints |
| `argparse` | stdlib | Agent CLI `wifi-file-server mount` subcommand -- project already uses argparse, no reason to switch |
| `asyncio` | stdlib | Agent event loop: reads local files, sends responses through WebSocket tunnel |
| `aiofiles` | `>=24.1.0` | Agent reads local files asynchronously for streaming through tunnel |
| `qrcode` | `>=8.0` | Generate QR code for mount URL (same as LAN mode) |
| `itsdangerous` | `>=2.2.0` | Mount code generation and validation with TTL expiry -- reuse existing token signing infra |
| `uvicorn[standard]` | `>=0.34.0` | Relay server runtime (same ASGI server) |
| `pydantic` | `>=2.10.0` | Request/response schemas for tunnel protocol messages |
| `jinja2` | `>=3.1.0` | Mount landing page (code entry + QR scan) -- same server-rendered pattern as share links |
| `httpx` | `>=0.28.0` (dev) | Testing relay server HTTP endpoints in integration tests |
| `httpx-ws` | `>=0.8.2` (dev) | Testing WebSocket tunnel endpoints in relay server |

## Tunnel Wire Protocol (Custom, No Library Needed)

The relay proxies browser HTTP requests to the agent over a single WebSocket connection. This requires a simple multiplexing protocol.

**Format:** JSON control frames + binary data frames over WebSocket.

```
Browser -> Relay:  normal HTTP request
Relay -> Agent (WS text):   {"id": "req-uuid", "method": "GET", "path": "/api/files", "headers": {...}, "query": "..."}
Agent -> Relay (WS text):   {"id": "req-uuid", "status": 200, "headers": {...}, "content_length": 4096}
Agent -> Relay (WS binary):  <16-byte request ID><chunk bytes>
Agent -> Relay (WS text):   {"id": "req-uuid", "done": true}
Relay -> Browser:  reconstructed HTTP StreamingResponse
```

- JSON text frames for control/metadata -- human-readable, debuggable.
- Binary frames for file content -- 16-byte UUID prefix identifies which request the chunk belongs to.
- Explicit `done` signal per request -- relay knows when to close the response stream.
- No need for msgpack or protobuf -- JSON overhead is negligible for metadata, and binary frames handle bulk data.

**Request multiplexing:** Tag each request/response pair with a UUID. The agent processes multiple requests concurrently using asyncio tasks. No WebSocket multiplexing extension needed -- just application-level request IDs.

**Upload handling (browser -> agent):** For file uploads, the relay streams the request body to the agent the same way but in reverse:

```
Relay -> Agent (WS text):   {"id": "req-uuid", "method": "POST", "path": "/api/files/upload", "headers": {...}, "content_length": 50000}
Relay -> Agent (WS binary):  <16-byte request ID><body chunk>
Relay -> Agent (WS text):   {"id": "req-uuid", "body_done": true}
Agent -> Relay (WS text):   {"id": "req-uuid", "status": 200, "headers": {...}}
```

## Installation

```bash
# Only one new production dependency
uv add "websockets>=16.0"

# No new dev dependencies needed -- httpx and httpx-ws already present
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `websockets` (agent client) | `aiohttp` client | `aiohttp` is a full HTTP framework -- massive dependency for just a WebSocket client. `websockets` is focused, lightweight, and better maintained for pure WebSocket use. |
| `websockets` (agent client) | `websocket-client` | `websocket-client` is synchronous by default. The agent needs async to handle concurrent requests through the tunnel. |
| `argparse` subcommands (CLI) | `typer` or `click` | Project already uses argparse. Adding a CLI framework dependency for one subcommand is unjustified. `add_subparsers()` works fine. |
| Custom tunnel protocol | `fastapi-websocket-rpc` | Adds abstraction we do not need. Our protocol is simple request/response pairs with IDs. RPC libraries add bidirectional call semantics, serialization layers, and reconnection logic we would fight against. |
| Custom tunnel protocol | `fastapi-proxy-lib` | Designed for HTTP-to-HTTP proxying, not HTTP-to-WebSocket tunneling. Does not solve our core problem. |
| JSON + binary frames | `msgpack` everywhere | JSON is human-readable for debugging the tunnel protocol. Binary frames already handle file content efficiently. msgpack saves bytes on metadata but adds a dependency and debugging friction for negligible gain. |
| Single `pyproject.toml` package | Separate relay server package | The relay server shares models, auth infra, and config with the existing server. Splitting into a separate package creates duplication. Keep it in the same package with separate entry points. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `aiohttp` | Heavyweight HTTP framework just for a WebSocket client | `websockets` -- focused, lightweight |
| `paramiko` / SSH tunneling | Wrong abstraction; SSH adds key management and encryption overhead we handle differently | Raw WebSocket tunnel |
| `ngrok` / tunnel services | External dependency, not embeddable, costs money at scale | Custom relay server |
| `protobuf` / `msgpack` | Over-engineering for wire format; JSON + binary frames are sufficient and debuggable | JSON text frames + binary data frames |
| `celery` / task queues | No background job queue needed; tunnel is synchronous request/response per connection | asyncio tasks for concurrent request handling |
| HTTP/2 multiplexing | Would require the agent to run an HTTP/2 server, defeating the outbound-only design | Application-level request IDs over WebSocket |
| `Textual` / `rich` for relay | Relay is a headless cloud server; no terminal UI needed | Standard logging |
| `redis` / `postgres` | No persistence needed; mount registry is in-memory per relay instance | In-memory dict of mount code -> WebSocket connection |
| `cryptography` / TLS certs | E2E encryption is deferred to v2 per PROJECT.md | Plain WebSocket (wss:// via reverse proxy in production) |
| `typer` / `click` | Project uses argparse; switching CLI frameworks for a subcommand wastes effort | `argparse.add_subparsers()` |

## Architecture Integration Points

### Relay Server (separate FastAPI app, same package)

The relay server is a **separate FastAPI application** with its own entry point, NOT a mode of the existing LAN server. Rationale:
- Different middleware stack (no file system access, no LAN auth middleware)
- Different deployment target (cloud VM vs local machine)
- Different security model (mount codes, not passwords)
- Shares code via Python imports, not by running in the same process

```
wifi-file-server serve ./folder     # existing LAN mode (unchanged)
wifi-file-server relay --port 443   # new relay server (cloud deployment)
wifi-file-server mount ./folder     # new agent connecting to relay
```

### Agent CLI (new subcommand, same package)

The agent is a subcommand of the existing CLI. It:
- Opens an outbound WebSocket to the relay using `websockets` library
- Registers with a mount code received from the relay
- Receives proxied HTTP requests via the tunnel protocol
- Reads local files with `aiofiles` and streams responses back as binary frames
- Reuses `ServerConfig` for shared folder path validation
- Reuses `qrcode` to display mount URL QR code in terminal
- Reuses `file_service` to list/read/serve files from the shared folder

### CLI Structure Change: argparse Subcommands

The existing CLI uses a flat argparse parser. v1.2 converts to subcommands:

```python
# Before (v1.1)
parser.add_argument("folder", ...)
parser.add_argument("--port", ...)

# After (v1.2)
subparsers = parser.add_subparsers(dest="command")

serve_parser = subparsers.add_parser("serve")  # default, backward-compat
serve_parser.add_argument("folder", ...)
serve_parser.add_argument("--port", ...)
# ... all existing flags

mount_parser = subparsers.add_parser("mount")
mount_parser.add_argument("folder", ...)
mount_parser.add_argument("--relay", required=True)  # relay server URL
mount_parser.add_argument("--password", ...)          # per-mount password
mount_parser.add_argument("--ttl", type=int)          # auto-expire seconds

relay_parser = subparsers.add_parser("relay")
relay_parser.add_argument("--port", type=int)
relay_parser.add_argument("--host", type=str)
```

**Backward compatibility:** If no subcommand is given and a folder path is the first positional argument, default to `serve` behavior. This preserves `wifi-file-server ./folder` working unchanged.

### Shared Code Reuse

| Module | Used By | Purpose |
|--------|---------|---------|
| `server.app.config.ServerConfig` | Agent | Validate shared folder path |
| `server.app.services.qr_service` | Agent | Display mount URL QR in terminal |
| `server.app.services.file_service` | Agent | List/read files from shared folder |
| `server.app.models.enums` | Agent + Relay | Shared enum types for tunnel protocol message types |
| `server.app.models.schemas` | Agent + Relay | Pydantic models for tunnel request/response messages |
| `itsdangerous` | Relay | Generate and validate mount codes with TTL |
| `jinja2` | Relay | Mount landing page with code entry and QR scan |

### New Modules (expected)

| Module | Component | Purpose |
|--------|-----------|---------|
| `server/relay/app.py` | Relay | Separate FastAPI app for the relay server |
| `server/relay/tunnel.py` | Relay | WebSocket tunnel manager -- maps mount codes to agent connections |
| `server/relay/routes.py` | Relay | HTTP catch-all that proxies to agent via tunnel |
| `server/agent/client.py` | Agent | WebSocket client that connects to relay and handles tunneled requests |
| `server/agent/handler.py` | Agent | Processes tunneled HTTP requests against local filesystem |
| `server/tunnel/protocol.py` | Shared | Pydantic models for tunnel wire protocol messages |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `websockets>=16.0` | Python `>=3.10` | Matches project's `>=3.11` requirement |
| `websockets>=16.0` | `uvicorn[standard]>=0.34.0` | No conflict; uvicorn already depends on `websockets` for its WebSocket protocol implementation, so the dependency is likely already installed |
| `fastapi>=0.115.0` | Starlette WebSocket | WebSocket support is mature; `send_bytes`/`receive_bytes` available for binary frames |

## Key Technical Decisions

### Binary Streaming for File Content

FastAPI/Starlette WebSocket supports `send_bytes()` / `receive_bytes()`. The agent streams file chunks as binary frames with a fixed-length 16-byte request-ID prefix (UUID bytes). This avoids base64-encoding file content into JSON, which would roughly double bandwidth usage.

### Chunked Transfer for Large Files

Files are streamed in 64KB chunks through the tunnel, not loaded entirely into memory. The agent reads with `aiofiles` in chunks and sends each chunk as a binary WebSocket frame. The relay reconstructs a `StreamingResponse` for the browser, yielding chunks as they arrive over the WebSocket.

### No `websockets` Dependency on Relay Side

The relay server uses FastAPI/Starlette's built-in WebSocket support (which internally uses `websockets` via uvicorn). Adding `websockets` as a direct dependency is only needed for the agent's outbound client connection.

### Mount Code via itsdangerous (Reuse Existing Infra)

Mount codes are short, human-readable codes (e.g., 6 alphanumeric chars) that map to an agent connection on the relay. The relay generates them when an agent connects. TTL expiry reuses `itsdangerous.URLSafeTimedSerializer` with `max_age` -- the same pattern already used for share links in v1.1.

### In-Memory Mount Registry

The relay keeps an in-memory `dict[str, WebSocket]` mapping mount codes to agent WebSocket connections. No database needed -- if the relay restarts, agents reconnect and get new codes. This matches the project's existing pattern of in-memory state (share links, clipboard, device list).

## Updated pyproject.toml Dependencies

```toml
[project]
dependencies = [
    # Existing (unchanged)
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0",
    "python-multipart>=0.0.20",
    "aiofiles>=24.1.0",
    "qrcode>=8.0",
    "ifaddr>=0.2.0",
    "zipstream-ng>=1.9.0",
    "bcrypt>=5.0.0",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.0",
    # NEW for v1.2
    "websockets>=16.0",           # Agent WebSocket client
]
```

## Sources

- [websockets 16.0 documentation](https://websockets.readthedocs.io/en/stable/) -- verified version 16.0, Python >=3.10, asyncio-native client API
- [websockets PyPI](https://pypi.org/project/websockets/) -- version 16.0 released 2026-01-10
- [FastAPI WebSocket reference](https://fastapi.tiangolo.com/reference/websockets/) -- send_bytes/receive_bytes API, connection lifecycle
- [FastAPI WebSocket advanced docs](https://fastapi.tiangolo.com/advanced/websockets/) -- server-side WebSocket patterns
- [wsrtunnel GitHub](https://github.com/defreng/wsrtunnel) -- reference implementation for HTTP-over-WebSocket reverse tunnel pattern
- [fastapi-websocket-rpc PyPI](https://pypi.org/project/fastapi-websocket-rpc/) -- considered and rejected (too much abstraction)
- [fastapi-proxy-lib GitHub](https://github.com/WSH032/fastapi-proxy-lib) -- considered and rejected (HTTP-to-HTTP only)
- [msgpack PyPI](https://pypi.org/project/msgpack/) -- v1.1.2, considered and rejected
- [httpx PyPI](https://pypi.org/project/httpx/) -- v0.28.1, already in dev deps

---
*Stack research for: v1.2 Remote Mounts relay server and agent CLI*
*Researched: 2026-03-11*
