# Phase 09: Relay Server - Research

**Researched:** 2026-03-11
**Domain:** FastAPI WebSocket proxying, in-memory mount registry, Jinja2 server-rendered templates, asyncio streaming
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Landing page:**
- Code entry only — simple text input for mount code + submit button, no in-browser QR scanner
- Server-rendered via Jinja2 templates (FastAPI + Jinja2)
- Informational style — brief explanation of Network File Server, how mount codes work, plus the code input
- On valid code submission: 302 redirect to `/m/{code}/`

**Error pages:**
- Shared `base.html` Jinja2 template — landing page and all error pages extend it for consistent styling
- "Not found" error page includes a code input field so users can try a different code without going back
- Distinct "offline" message — "This mount is currently offline. The owner may reconnect soon." — distinguishes from invalid code
- "Expired" error template created now (ready for Phase 11 TTL) — shows clear expired message
- Three distinct error states: not_found, offline, expired

**Request proxying:**
- Streaming passthrough — relay streams tunnel frames directly to browser via StreamingResponse async generator from stream queue
- Full bidirectional proxying — all HTTP methods (GET, POST, PUT, DELETE) forwarded through tunnel, including request bodies for uploads
- Minimal header rewriting — strip hop-by-hop headers (Connection, Transfer-Encoding), rewrite Host, preserve cookies for Phase 11 auth pass-through
- Active CANCEL on browser disconnect — relay sends CANCEL frame to agent immediately when browser drops connection
- 30-second first-byte timeout inherited from TunnelConnection (decided in Phase 8)

### Claude's Discretion
- Mount code format (length, characters, generation algorithm)
- Relay app internal structure (routers, services, middleware organization)
- Mount registry data structure and cleanup strategy
- Agent WebSocket endpoint design
- Jinja2 template content and CSS styling details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RELY-01 | Relay server maintains in-memory mount registry mapping codes to agent WebSocket connections | `MountRegistry` service with dict[str, TunnelConnection] + MountStatus enum. Pattern mirrors ShareLinkService. Cleanup on WebSocket disconnect. |
| RELY-02 | Browser HTTP requests to `/m/{code}/*` are proxied through the tunnel to the correct agent | FastAPI wildcard route `@router.api_route("/m/{code}/{path:path}")` + `StreamingResponse` with async generator consuming `TunnelConnection.read_stream_iter()`. CANCEL frame on `Request.is_disconnected()`. |
| RELY-03 | Mount landing page allows users to enter a code or scan QR to access a mount | Jinja2 `TemplateResponse` on `GET /` — form submits code via `GET /?code=XXX` then redirects 302 to `/m/{code}/`. Template extends `base.html`. |
| RELY-04 | Clean error pages display when a mount is offline, expired, or not found | Three templates (not_found.html, offline.html, expired.html) extending base.html. All returned by the proxy router as `TemplateResponse` with appropriate HTTP status codes. |
</phase_requirements>

## Summary

Phase 9 builds the relay application as a standalone FastAPI app (`relay/app/`) that lives alongside `server/` and `tunnel/` in the monorepo. It has three responsibilities: (1) accept agent WebSocket connections and register mount codes in an in-memory registry, (2) proxy browser HTTP requests at `/m/{code}/*` through `TunnelConnection` using `StreamingResponse` and async generators, and (3) serve a Jinja2 landing page and three error pages.

Every building block needed already exists in the project: `TunnelConnection` (Phase 8), `Jinja2Templates` (already used in `server/app/routers/share.py`), the `create_app()` factory pattern (`server/app/main.py`), and the typed exception + service layer pattern (`share_service.py`). The relay simply wires these together in a new top-level package. No new dependencies are required — `fastapi`, `jinja2`, and `uvicorn` are already in `pyproject.toml`.

The trickiest implementation challenge is bidirectional streaming with disconnect detection: the async generator that feeds `StreamingResponse` must also race against `Request.is_disconnected()` and send a CANCEL frame when the browser drops before the response finishes.

**Primary recommendation:** Mirror the `server/` package structure exactly. Service: `MountRegistry`. Routers: `agent_ws.py` (WebSocket endpoint for agents), `mount_proxy.py` (HTTP proxy + error pages), `landing.py` (landing page). App factory: `relay/app/main.py` with `create_relay_app()`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.135.1 (already in project) | App factory, routers, WebSocket, StreamingResponse | Already project dependency |
| `jinja2` | 3.1+ (already in project) | Server-rendered landing page and error pages | Already project dependency; used by share router |
| `uvicorn` | 0.34+ (already in project) | ASGI server for relay | Already project dependency |
| `tunnel` (local) | Phase 8 implementation | TunnelConnection, frames, protocol, exceptions | All tunnel multiplexing logic lives here |
| `secrets` | stdlib | Mount code generation | `secrets.token_urlsafe` gives URL-safe random strings |
| `asyncio` | stdlib | Disconnect race detection with `Request.is_disconnected()` | Already used throughout |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `starlette.requests.Request` | via fastapi | `is_disconnected()` for browser disconnect detection | Called in proxy async generator to detect when browser drops |
| `starlette.websockets.WebSocketDisconnect` | via fastapi | Catch agent WebSocket disconnects | In agent WebSocket endpoint to clean up registry |
| `fastapi.responses.StreamingResponse` | via fastapi | Stream tunnel frames to browser | Proxy endpoint response type |
| `fastapi.responses.RedirectResponse` | via fastapi | 302 redirect after mount code submission | Landing page code-entry form handler |
| `qrcode` | 8.0+ (already in project) | SVG QR for landing page display | Optional — landing page can show QR for entered code |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `secrets.token_urlsafe` for codes | `uuid.uuid4()` | uuid4 codes are too long (36 chars); urlsafe codes can be truncated to 8 chars — better UX |
| `Request.is_disconnected()` polling | Catching `asyncio.CancelledError` | Polling is explicit and testable; CancelledError relies on Starlette internals cancelling the generator |
| Single catch-all route for proxy | Separate routes per method | Single `api_route(..., methods=["GET", "POST", "PUT", "DELETE", "PATCH"])` is cleaner and matches CONTEXT.md requirement |

**Installation:** No new packages required. All dependencies already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure
```
relay/
├── __init__.py
└── app/
    ├── __init__.py
    ├── main.py              # create_relay_app() factory
    ├── enums.py             # MountStatus enum
    ├── exceptions.py        # MountNotFoundError, MountOfflineError, MountExpiredError
    ├── routers/
    │   ├── __init__.py
    │   ├── agent_ws.py      # WebSocket endpoint for agents at /agent/ws
    │   ├── mount_proxy.py   # HTTP proxy at /m/{code}/{path:path}
    │   └── landing.py       # Landing page and code-entry at GET /
    └── services/
        ├── __init__.py
        └── mount_registry.py  # MountRegistry service (in-memory dict)

relay/templates/
├── base.html        # shared layout
├── landing.html     # extends base — code input + explanation
├── not_found.html   # extends base — code input + "not found"
├── offline.html     # extends base — "mount is offline"
└── expired.html     # extends base — "mount has expired" (Phase 11 ready)

tests/relay/
├── __init__.py
├── conftest.py          # relay app fixture, MockTunnelConnection
├── test_mount_registry.py
├── test_mount_proxy.py
└── test_landing.py
```

### Pattern 1: MountRegistry Service
**What:** In-memory dict mapping mount codes to `TunnelConnection` instances with a `MountStatus` enum per entry.
**When to use:** Created as a module-level singleton (same pattern as `connection_manager.py` in the server). Agent WebSocket endpoint registers/deregisters; proxy router does lookup.
**Example:**
```python
# Source: mirrors server/app/services/share_service.py pattern + connection_manager.py pattern
from dataclasses import dataclass
from relay.app.enums import MountStatus
from relay.app.exceptions import MountNotFoundError, MountOfflineError, MountExpiredError
from tunnel.connection import TunnelConnection


@dataclass
class MountRecord:
    code: str
    connection: TunnelConnection
    status: MountStatus


class MountRegistry:
    def __init__(self) -> None:
        self._mounts: dict[str, MountRecord] = {}

    def register(self, code: str, connection: TunnelConnection) -> None:
        if not code:
            raise ValueError("Mount code must not be empty")
        self._mounts[code] = MountRecord(code=code, connection=connection, status=MountStatus.ONLINE)

    def deregister(self, code: str) -> None:
        if code not in self._mounts:
            raise MountNotFoundError(code)
        del self._mounts[code]

    def get_connection(self, code: str) -> TunnelConnection:
        record = self._mounts.get(code)
        if record is None:
            raise MountNotFoundError(code)
        if record.status == MountStatus.OFFLINE:
            raise MountOfflineError(code)
        if record.status == MountStatus.EXPIRED:
            raise MountExpiredError(code)
        return record.connection
```

### Pattern 2: Agent WebSocket Endpoint
**What:** `GET /agent/ws?code=XXX` — agent connects here, relay wraps the WebSocket in `TunnelConnection`, registers it, runs heartbeat and receive loop.
**When to use:** This is the entry point for Phase 10 agents.
**Example:**
```python
# Source: mirrors server/app/routers/websocket.py pattern
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from relay.app.services.mount_registry import get_registry
from tunnel.connection import TunnelConnection
from tunnel.constants import HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT
import secrets

router = APIRouter()

@router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    code: str = Query(...),
) -> None:
    await websocket.accept()
    registry = get_registry()
    conn = TunnelConnection(websocket)
    registry.register(code, conn)
    conn.start_heartbeat(HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)
    try:
        await conn.run_receive_loop()
    except WebSocketDisconnect:
        pass
    finally:
        await conn.close()
        try:
            registry.deregister(code)
        except MountNotFoundError:
            pass  # already deregistered
```

### Pattern 3: HTTP Proxy with StreamingResponse
**What:** Relay receives browser HTTP request, serializes metadata into OPEN frame, streams response DATA frames back as `StreamingResponse`, detects disconnect and sends CANCEL.
**When to use:** Every browser request to `/m/{code}/{path:path}`.
**Example:**
```python
# Source: FastAPI StreamingResponse + TunnelConnection.read_stream_iter() from Phase 8
import uuid
import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from tunnel.constants import FIRST_BYTE_TIMEOUT_S
from tunnel.exceptions import FirstByteTimeoutError

router = APIRouter()

HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})

@router.api_route(
    "/m/{code}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_request(request: Request, code: str, path: str) -> StreamingResponse:
    registry = get_registry()
    try:
        conn = registry.get_connection(code)
    except MountNotFoundError:
        return templates.TemplateResponse(request, "not_found.html", status_code=404)
    except MountOfflineError:
        return templates.TemplateResponse(request, "offline.html", status_code=503)
    except MountExpiredError:
        return templates.TemplateResponse(request, "expired.html", status_code=410)

    request_id = uuid.uuid4()
    body = await request.body()

    # Forward headers — strip hop-by-hop, rewrite Host
    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    forward_headers["host"] = request.url.hostname or ""

    metadata = {
        "method": request.method,
        "path": f"/{path}",
        "query": str(request.url.query),
        "headers": forward_headers,
        "body": body.decode("latin-1") if body else "",
    }

    conn.open_stream(request_id)
    await conn.send_open(request_id, metadata)

    async def stream_generator():
        try:
            # First byte timeout
            first = await conn.read_stream(request_id, FIRST_BYTE_TIMEOUT_S)
            yield first

            async for chunk in conn.read_stream_iter(request_id):
                if await request.is_disconnected():
                    await conn.send_cancel(request_id)
                    return
                yield chunk
        except FirstByteTimeoutError:
            yield b""  # StreamingResponse needs at least something; upstream sees empty
        finally:
            # Ensure CANCEL sent if browser disconnected before generator finished
            if await request.is_disconnected():
                try:
                    await conn.send_cancel(request_id)
                except Exception:
                    pass

    return StreamingResponse(stream_generator(), media_type="application/octet-stream")
```

### Pattern 4: Landing Page Code Entry (302 Redirect)
**What:** `GET /` renders the landing page. `GET /?code=XXX` redirects 302 to `/m/{code}/`.
**When to use:** User navigates to relay root URL.
**Example:**
```python
# Source: mirrors server/app/routers/share.py Jinja2Templates pattern
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory=str(_RELAY_TEMPLATES_DIR))

@router.get("/")
async def landing_page(request: Request, code: str = "") -> Response:
    if code:
        # Validate format only — registry lookup happens at /m/{code}/
        return RedirectResponse(url=f"/m/{code}/", status_code=302)
    return templates.TemplateResponse(request, "landing.html")
```

### Pattern 5: Mount Code Generation
**What:** 8-character URL-safe random string using `secrets.token_urlsafe`.
**When to use:** Generated by the relay when an agent connects (or by the agent itself and sent as the `code` query param).
**Example:**
```python
# Source: Python stdlib secrets documentation
import secrets

def generate_mount_code() -> str:
    """Generate an 8-character URL-safe mount code.

    Uses secrets.token_urlsafe (base64url alphabet: A-Z, a-z, 0-9, -, _).
    Returns exactly 8 characters. Statistically unique for session-lifetime use.
    """
    # token_urlsafe(6) produces 8 base64url characters from 6 random bytes
    return secrets.token_urlsafe(6)
```

### Anti-Patterns to Avoid
- **Importing `server/` modules from `relay/`:** The relay is a separate FastAPI app. It imports from `tunnel/` (shared) but NOT from `server/`. No cross-app imports.
- **Using a mutable module-level singleton for `MountRegistry` without a setter function:** Tests need to inject a fresh registry. Follow the `get_share_service` / `set_share_service` pattern from `share_service.py`.
- **Blocking the event loop in the proxy generator:** The `stream_generator` must use `await` throughout. Never call `queue.get_nowait()` in a hot loop — use `read_stream_iter` which correctly uses `asyncio.wait`.
- **Not stripping Transfer-Encoding before forwarding to browser:** The agent may include `Transfer-Encoding: chunked`; relay handles chunking via StreamingResponse. Forwarding it causes double-chunking and browser parse errors.
- **Registering the mount AFTER accepting the WebSocket:** Register should happen immediately after `accept()` so browser requests that race in during the handshake find the connection.
- **Using `string` comparisons for MountStatus:** Use `MountStatus(str, Enum)` — enforced by project CLAUDE.md requirements.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP proxying frame format | Custom binary proxy protocol | `TunnelConnection.send_open` / `read_stream_iter` | Phase 8 already implements all stream lifecycle |
| Streaming response | Manual `send` loops | `StreamingResponse` with async generator | Starlette handles chunked transfer, connection cleanup |
| Disconnect detection | Manual polling timer | `Request.is_disconnected()` | Starlette polls the ASGI receive channel correctly |
| Mount code uniqueness | UUID + collision check | `secrets.token_urlsafe(6)` | 48 bits of entropy; collision probability negligible for session-lifetime codes |
| Template inheritance | Copy-paste HTML per page | Jinja2 `{% extends "base.html" %}` + `{% block %}` | Already used by existing templates pattern |
| Hop-by-hop header list | Hardcoded string matching | Defined `frozenset` constant | Standard RFC 2616 list; don't invent custom filtering |

**Key insight:** The tunnel multiplexing, heartbeat, and stream lifecycle are all in `TunnelConnection` (Phase 8). The relay's job is routing and HTTP protocol adaptation, not re-implementing any tunnel mechanics.

## Common Pitfalls

### Pitfall 1: StreamingResponse body for error pages returns wrong content-type
**What goes wrong:** When `get_connection()` raises and you return a `TemplateResponse` from an `api_route` typed to return `StreamingResponse`, mypy and FastAPI may mismatch.
**Why it happens:** `api_route` infers the response class from the first successful branch.
**How to avoid:** Type the return annotation as `Response` (base class). Both `TemplateResponse` and `StreamingResponse` extend `Response`.
**Warning signs:** `422 Unprocessable Entity` in tests, or mypy type errors.

### Pitfall 2: Browser receives first chunk before response headers are sent
**What goes wrong:** When the agent sends a response with custom status code (e.g., 404 from the underlying file server), the relay unconditionally returns 200 from `StreamingResponse`.
**Why it happens:** The OPEN frame from the agent carries HTTP metadata back including status; relay must extract it and pass `status_code` to `StreamingResponse`.
**How to avoid:** Design the OPEN frame payload returned by the agent to include `{"status": 200, "headers": {...}}`. Parse this in the relay before starting the stream generator. The first DATA frame is the body, not metadata.
**Warning signs:** All proxied responses appear as 200 even when the underlying file was not found.

### Pitfall 3: Registry cleanup race between heartbeat timeout and explicit deregister
**What goes wrong:** Heartbeat tears down the `TunnelConnection` while the WebSocket endpoint's `finally` block also calls `deregister()` — second call raises `MountNotFoundError`.
**Why it happens:** Teardown can be triggered from two paths (heartbeat timeout, WebSocket disconnect).
**How to avoid:** `deregister()` should be silent (no-op) if the code is already gone, or the `finally` block wraps in `try/except MountNotFoundError`. CONTEXT.md already suggests this pattern for the agent WS endpoint.
**Warning signs:** Unhandled `MountNotFoundError` in logs on agent disconnect.

### Pitfall 4: Request body consumed before forwarding
**What goes wrong:** `await request.body()` in the proxy handler consumes the body, but if it's called after the streaming has started, the body is unavailable.
**Why it happens:** FastAPI/Starlette streams the request body lazily.
**How to avoid:** Call `await request.body()` at the top of the handler, before any async work. This buffers the complete body for inclusion in the OPEN frame metadata. This is acceptable since the 64 KB frame limit bounds the per-frame size and large uploads will be chunked by the agent.
**Warning signs:** Empty body forwarded for POST/PUT requests, causing upload failures.

### Pitfall 5: Jinja2 templates directory resolution in relay app
**What goes wrong:** Template path resolves relative to wrong directory when relay runs from project root.
**Why it happens:** `Path(__file__)` in `relay/app/main.py` resolves differently than in `server/app/routers/share.py`.
**How to avoid:** Mirror the `share.py` pattern exactly — resolve template path relative to `Path(__file__).resolve().parent.parent.parent / "relay" / "templates"` (or equivalent absolute path from `relay/app/main.py`).
**Warning signs:** `TemplateNotFound` error when running relay.

## Code Examples

### MountStatus Enum
```python
# Source: mirrors server/app/models/enums.py pattern (str, Enum)
from enum import Enum

class MountStatus(str, Enum):
    """Lifecycle status of a registered mount."""
    ONLINE = "online"
    OFFLINE = "offline"
    EXPIRED = "expired"
```

### Mount Registry Exceptions
```python
# Source: mirrors server/app/exceptions.py pattern
class MountNotFoundError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mount not found: {code}")

class MountOfflineError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mount is offline: {code}")

class MountExpiredError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mount has expired: {code}")
```

### Relay App Factory
```python
# Source: mirrors server/app/main.py create_app() pattern
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from relay.app.routers.agent_ws import router as agent_router
from relay.app.routers.mount_proxy import router as proxy_router
from relay.app.routers.landing import router as landing_router

def create_relay_app() -> FastAPI:
    app = FastAPI(title="Network File Server Relay")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(agent_router)
    app.include_router(proxy_router)
    app.include_router(landing_router)
    return app

app = create_relay_app()
```

### Base Jinja2 Template Pattern
```html
<!-- relay/templates/base.html — shared layout for all pages -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Network File Server{% endblock %}</title>
    <style>
        /* System font stack, light/dark mode — mirrors share_download.html style */
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               display: flex; justify-content: center; align-items: center;
               min-height: 100vh; padding: 1rem; background: #f5f5f5; color: #1a1a1a; }
        .card { background: #fff; border-radius: 12px; padding: 2.5rem;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08); max-width: 440px; width: 100%; }
        @media (prefers-color-scheme: dark) {
            body { background: #111; color: #e5e5e5; }
            .card { background: #1e1e1e; }
        }
    </style>
</head>
<body>
    <div class="card">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

### Disconnect-Racing Streaming Generator
```python
# Source: Starlette Request.is_disconnected() is async (verified locally)
# Pattern: poll disconnect between chunks
async def stream_generator(
    request: Request,
    conn: TunnelConnection,
    request_id: uuid.UUID,
) -> AsyncGenerator[bytes, None]:
    cancelled = False
    try:
        first_chunk = await conn.read_stream(request_id, FIRST_BYTE_TIMEOUT_S)
        yield first_chunk

        async for chunk in conn.read_stream_iter(request_id):
            if await request.is_disconnected():
                cancelled = True
                await conn.send_cancel(request_id)
                return
            yield chunk
    except FirstByteTimeoutError:
        # Relay returns empty body; upstream already got 502/504 via status handling
        return
    finally:
        if not cancelled and await request.is_disconnected():
            try:
                await conn.send_cancel(request_id)
            except Exception:
                pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `yield from` generators | `async def` + `async for` async generators | Python 3.6+ | `StreamingResponse` accepts async generators natively in Starlette |
| Polling `asyncio.sleep` for disconnect | `await Request.is_disconnected()` | Starlette 0.20+ | Correct ASGI-level disconnect detection without busy-waiting |
| `threading.Thread` for background tasks | `asyncio.create_task` (heartbeat in TunnelConnection) | Phase 8 | Already the pattern — relay just calls `conn.start_heartbeat()` |
| Shared app state via global vars | Module-level singleton + getter/setter | Established in project | `get_registry()` / `set_registry()` follows `get_share_service()` pattern |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Replaced by `lifespan` context manager in FastAPI 0.93+. However, since the mount registry has no startup initialization (it's just an empty dict), no lifespan handler is needed for this phase.

## Open Questions

1. **Who generates the mount code — relay or agent?**
   - What we know: CONTEXT.md says "Agent WebSocket endpoint design" is Claude's discretion. The agent connects via `GET /agent/ws?code=XXX`.
   - What's unclear: Does the agent generate its own code and pass it, or does the relay assign one and return it?
   - Recommendation: Agent generates its own code using `secrets.token_urlsafe(6)` and sends it as the `code` query parameter. This avoids a round-trip handshake before the WebSocket is established and gives Phase 10 control over code generation.

2. **Response metadata (status code, headers) from agent back to browser**
   - What we know: CONTEXT.md locks "streaming passthrough" but is silent on how the agent communicates HTTP status code and response headers back.
   - What's unclear: Is status + headers in the OPEN frame payload (sent by agent as the first frame), or in a separate JSON control message before data frames?
   - Recommendation: Agent sends a JSON text control message `{"type": "response_meta", "status": 200, "headers": {...}}` immediately after it receives the OPEN frame, before sending any DATA frames. Relay reads this via `receive_control()` before starting `StreamingResponse`. This avoids encoding HTTP metadata in binary DATA frames and keeps the pattern consistent with Phase 8 control messages.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and `testpaths = ["server/tests", "tests"]` |
| Quick run command | `uv run pytest tests/relay/ -x -q` |
| Full suite command | `uv run pytest server/tests/ tests/tunnel/ tests/relay/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RELY-01 | `register()` stores connection; `get_connection()` returns it | unit | `uv run pytest tests/relay/test_mount_registry.py::test_register_and_get -x` | Wave 0 |
| RELY-01 | `deregister()` removes mount; subsequent `get_connection()` raises `MountNotFoundError` | unit | `uv run pytest tests/relay/test_mount_registry.py::test_deregister -x` | Wave 0 |
| RELY-01 | `get_connection()` on OFFLINE mount raises `MountOfflineError` | unit | `uv run pytest tests/relay/test_mount_registry.py::test_offline_mount -x` | Wave 0 |
| RELY-02 | GET `/m/{code}/path` returns 200 and proxied response body via MockTunnelConnection | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_proxy_get -x` | Wave 0 |
| RELY-02 | POST `/m/{code}/path` with body forwards body in OPEN frame metadata | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_proxy_post_body -x` | Wave 0 |
| RELY-02 | When mount not found, proxy returns 404 with not_found template HTML | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_proxy_not_found -x` | Wave 0 |
| RELY-02 | When mount offline, proxy returns 503 with offline template HTML | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_proxy_offline -x` | Wave 0 |
| RELY-03 | `GET /` renders landing page with code input form | unit | `uv run pytest tests/relay/test_landing.py::test_landing_renders -x` | Wave 0 |
| RELY-03 | `GET /?code=XXXX` returns 302 redirect to `/m/XXXX/` | unit | `uv run pytest tests/relay/test_landing.py::test_code_redirect -x` | Wave 0 |
| RELY-04 | not_found.html contains code input field for retry | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_not_found_has_code_input -x` | Wave 0 |
| RELY-04 | expired.html renders without error | unit | `uv run pytest tests/relay/test_mount_proxy.py::test_expired_page -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/relay/ -x -q`
- **Per wave merge:** `uv run pytest server/tests/ tests/tunnel/ tests/relay/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `relay/__init__.py` — package root
- [ ] `relay/app/__init__.py`
- [ ] `relay/app/main.py` — `create_relay_app()` factory
- [ ] `relay/app/enums.py` — `MountStatus` enum
- [ ] `relay/app/exceptions.py` — `MountNotFoundError`, `MountOfflineError`, `MountExpiredError`
- [ ] `relay/app/services/__init__.py`
- [ ] `relay/app/services/mount_registry.py` — `MountRegistry` class + `get_registry()` / `set_registry()`
- [ ] `relay/app/routers/__init__.py`
- [ ] `relay/app/routers/agent_ws.py` — agent WebSocket endpoint
- [ ] `relay/app/routers/mount_proxy.py` — HTTP proxy + error page responses
- [ ] `relay/app/routers/landing.py` — landing page + code-entry redirect
- [ ] `relay/templates/base.html` — shared layout
- [ ] `relay/templates/landing.html` — informational + code input
- [ ] `relay/templates/not_found.html` — includes code input for retry
- [ ] `relay/templates/offline.html` — offline message
- [ ] `relay/templates/expired.html` — expired message
- [ ] `tests/relay/__init__.py`
- [ ] `tests/relay/conftest.py` — relay app fixture + MockTunnelConnection
- [ ] `tests/relay/test_mount_registry.py` — RELY-01 unit tests
- [ ] `tests/relay/test_mount_proxy.py` — RELY-02, RELY-04 unit tests
- [ ] `tests/relay/test_landing.py` — RELY-03 unit tests
- [ ] Add `relay` to `[tool.hatch.build.targets.wheel] packages` in `pyproject.toml`

## Sources

### Primary (HIGH confidence)
- `/Users/rahul/Projects/network-file-server/tunnel/connection.py` — TunnelConnection API: `open_stream`, `send_open`, `read_stream`, `read_stream_iter`, `send_cancel`, `close`, `start_heartbeat`, `run_receive_loop`
- `/Users/rahul/Projects/network-file-server/tunnel/protocol.py` — `WebSocketProtocol` interface
- `/Users/rahul/Projects/network-file-server/server/app/routers/share.py` — Jinja2Templates pattern, template path resolution, TemplateResponse usage
- `/Users/rahul/Projects/network-file-server/server/app/services/share_service.py` — service singleton pattern (get/set), typed exception hierarchy, dataclass registry entries
- `/Users/rahul/Projects/network-file-server/server/app/main.py` — `create_app()` factory pattern
- `/Users/rahul/Projects/network-file-server/server/app/models/enums.py` — `(str, Enum)` pattern for domain enums
- `/Users/rahul/Projects/network-file-server/server/app/routers/websocket.py` — FastAPI WebSocket endpoint pattern with `WebSocketDisconnect` handling
- `/Users/rahul/Projects/network-file-server/server/tests/conftest.py` — test fixture pattern (ASGITransport, AsyncClient)
- `/Users/rahul/Projects/network-file-server/pyproject.toml` — confirmed fastapi 0.115+, jinja2 3.1+, no new deps needed
- Locally verified: `starlette.requests.Request.is_disconnected` is an async method (Python 3.11, FastAPI 0.135.1)
- Locally verified: `fastapi.responses.StreamingResponse` accepts async generators as `content`
- Locally verified: `secrets.token_urlsafe(6)` produces 8-character URL-safe strings

### Secondary (MEDIUM confidence)
- RFC 2616 Section 13.5.1 — standard hop-by-hop header list (Connection, Keep-Alive, TE, Trailers, Transfer-Encoding, Upgrade, Proxy-Authenticate, Proxy-Authorization)
- FastAPI documentation — `@router.api_route()` supports `methods` list for multi-method routes

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all existing project dependencies, no new packages, verified locally
- Architecture: HIGH — directly derived from locked CONTEXT.md decisions + existing project patterns
- Pitfalls: HIGH — derived from Starlette/asyncio internals and verified against existing code
- Test infrastructure: HIGH — pytest-asyncio already configured, `testpaths` already includes `tests/`

**Research date:** 2026-03-11
**Valid until:** 2026-09-11 (FastAPI/Starlette APIs are stable; `TunnelConnection` API is Phase 8 output)
