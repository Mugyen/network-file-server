# Phase 10: Agent CLI - Research

**Researched:** 2026-03-11
**Domain:** Python CLI + WebSocket client + in-process ASGI proxying
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**CLI structure:**
- Subcommand pattern: `wifi-file-server mount ./files --server <url>`
- Existing bare positional `wifi-file-server ./files` stays unchanged for LAN mode (no breaking change)
- `--server` flag is required for mount subcommand (relay URL)
- `--name` flag is optional (human-readable mount name, defaults to folder name)
- Mount code assigned by relay server (agent does not request a specific code)

**Request proxying:**
- In-process ASGI transport: call `create_app()` in-process, use `httpx.AsyncClient` with `ASGITransport` — no port binding, no network hop
- Stream response bodies back through tunnel as DATA frames (essential for large file downloads)
- Stream request bodies from tunnel frames as async iterator to httpx (essential for large uploads)
- Handle CANCEL frames from relay — abort in-flight httpx request and clean up the stream when browser disconnects

**Terminal UX:**
- After successful mount: display mount URL, QR code (reuse `qr_service`), mount code, sharing folder, relay URL, and status line
- Minimal activity indicators: show brief line per proxied request (e.g., `GET /api/files 200`)
- Display running request count and connection duration (uptime)
- Graceful shutdown on Ctrl+C: print "Unmounting...", send clean disconnect to relay, deregister mount, then exit

**Reconnection behavior:**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AGNT-01 | User can mount a local directory via `wifi-file-server mount ./files --server <url>` | argparse subcommand pattern; `_build_parser()` extension in `server/app/cli.py` |
| AGNT-02 | Agent starts local FastAPI server using `create_app()` and proxies tunneled requests via httpx | `httpx.AsyncClient` + `ASGITransport(app=create_app())`; parse OPEN frame metadata; send DATA+CLOSE frames back |
| AGNT-03 | Agent displays mount URL and QR code in terminal after successful connection | Reuse `generate_ascii_qr()` from `server/app/services/qr_service.py`; mount URL is `{relay_url}/m/{code}` |
| AGNT-04 | Agent auto-reconnects on WebSocket drop with exponential backoff and jitter | `websockets` v16 client library; manual reconnect loop with `asyncio.sleep`; update terminal status line |
</phase_requirements>

---

## Summary

Phase 10 builds the agent-side CLI that connects to an already-complete relay server (Phase 9). The agent opens an outbound WebSocket to `/agent/ws` on the relay, receives a relay-assigned mount code via a JSON control message, then enters a receive loop handling OPEN frames. For each OPEN frame it calls `create_app()` in-process via `httpx.AsyncClient(transport=ASGITransport(...))`, streams the response body back as DATA frames, and closes with a CLOSE frame.

The existing codebase already provides all the building blocks: `TunnelConnection` for multiplexing, `create_app()` for the local ASGI app, `generate_ascii_qr()` for QR display, and `serialize_frame/deserialize_frame` for wire encoding. The agent is primarily a wiring task: extend the CLI parser with a `mount` subcommand, write a `WebSocketAdapter` shim so `websockets.ClientConnection` satisfies the `WebSocketProtocol` interface, and implement the OPEN-frame handler loop.

A critical integration point is that the relay's `agent_ws.py` currently requires a `?code=...` query parameter but CONTEXT says the relay assigns the code. This means `agent_ws.py` must be modified to generate the code, register the mount, then send a `{"type": "mount_registered", "code": "..."}` control message — and the agent receives it before starting the receive loop.

**Primary recommendation:** Add `agent/` package alongside `server/`, `relay/`, `tunnel/`. CLI parser gets a `mount` subcommand. Relay's `agent_ws.py` generates and sends the code. Agent wraps `websockets.ClientConnection` in an adapter, uses `TunnelConnection` for frame I/O, and dispatches OPEN frames to a local httpx ASGI client.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| websockets | 16.0 (already in venv) | Client-side WebSocket connection to relay | Already installed via httpx-ws; provides asyncio-native connect with auto-reconnect iterator |
| httpx | 0.28.1 (already in pyproject dev dep) | In-process ASGI request dispatch | Must be moved from dev to production dependency; `ASGITransport` enables zero-hop proxying |
| asyncio | stdlib | Concurrent request handling, backoff sleep | Standard; used throughout existing codebase |
| argparse | stdlib | CLI subcommand parser | Already used in `server/app/cli.py`; extend with subparsers |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| qrcode | >=8.0 (already in deps) | ASCII QR code for terminal display | Reuse `generate_ascii_qr()` from `server/app/services/qr_service.py` |
| datetime / time | stdlib | Uptime display, reconnect delay | Formatting connection duration in status line |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| websockets v16 | aiohttp WebSocket client | websockets already in venv; aiohttp is heavier and not installed |
| httpx ASGITransport | spawn uvicorn on random port | ASGITransport is zero-overhead, no OS port, no network hop — strictly better |
| manual backoff loop | websockets built-in iterator reconnect | Built-in iterator lacks "send previous code on reconnect" logic needed here |

**Installation (httpx must move from dev to production):**
```bash
# In pyproject.toml: move httpx from [dependency-groups.dev] to [project.dependencies]
# Then:
uv sync
```

---

## Architecture Patterns

### Recommended Project Structure

```
agent/
├── __init__.py
├── cli.py           # mount subcommand entry point (called from server/app/cli.py)
├── connection.py    # AgentConnection — WebSocket adapter + reconnect loop
├── proxy.py         # handle_open_frame() — ASGI proxy dispatch for one stream
└── display.py       # terminal output: print_mounted(), print_request(), print_status()

tests/agent/
├── __init__.py      # NO __init__.py to avoid shadowing (per project pattern)
│   — WRONG: do NOT add __init__.py here (project convention from STATE.md)
├── conftest.py
├── test_connection.py
├── test_proxy.py
└── test_display.py
```

**Correction:** Following the pattern from STATE.md decisions, `tests/agent/` should NOT have an `__init__.py` to prevent sys.path shadowing of the real `agent/` package.

Corrected structure:
```
tests/agent/
├── conftest.py      # (no __init__.py — matches tests/tunnel/ and tests/relay/ pattern)
├── test_connection.py
├── test_proxy.py
└── test_display.py
```

### Pattern 1: CLI Subcommand Extension

**What:** Add `subparsers` to the existing `_build_parser()` in `server/app/cli.py`, or restructure to a top-level subcommand dispatcher.
**When to use:** `wifi-file-server mount` — distinguishes remote mode from LAN mode without breaking existing positional arg.

**How existing parser must change:**
The current `_build_parser()` uses a bare positional `folder` argument. To add `mount` as a subcommand without breaking `wifi-file-server ./files`, the parser must become a subcommand-aware dispatcher. The bare `wifi-file-server ./files` invocation (no subcommand) should remain the default path.

**Approach (backward-compatible):**
```python
# Source: argparse stdlib docs
parser = argparse.ArgumentParser(...)
subparsers = parser.add_subparsers(dest="command")

# Mount subcommand
mount_parser = subparsers.add_parser("mount", help="Mount a local directory via relay")
mount_parser.add_argument("folder", help="Path to the folder to share")
mount_parser.add_argument("--server", required=True, help="Relay server URL")
mount_parser.add_argument("--name", help="Human-readable mount name (defaults to folder name)")

# In main(): if args.command == "mount": run_mount(args) else: run_lan_server(args)
# Bare invocation with no subcommand: args.command is None — fall through to LAN mode
# BUT: bare `wifi-file-server ./files` will fail because `folder` is now only on mount subparser
```

**Critical issue:** The existing bare positional `wifi-file-server ./files` cannot coexist with subparsers using the same positional name. The clearest pattern is to keep the old `folder` as a top-level positional with `nargs='?'` (optional), and check `args.command` to dispatch.

### Pattern 2: WebSocket Adapter for TunnelConnection

**What:** `websockets.ClientConnection` API uses `send(bytes|str)` and `recv(decode=None)`. `TunnelConnection` expects `WebSocketProtocol` with `send_bytes`, `send_text`, `receive_bytes`, `receive_text`, `receive`.
**When to use:** Wrapping the outbound `websockets` connection so `TunnelConnection` can be reused as-is.

```python
# Source: verified against websockets v16 API + tunnel/protocol.py
from websockets.asyncio.client import ClientConnection
from tunnel.protocol import WebSocketProtocol  # structural Protocol

class WebSocketClientAdapter:
    """Adapts websockets.ClientConnection to satisfy WebSocketProtocol."""

    def __init__(self, ws: ClientConnection) -> None:
        if not isinstance(ws, ClientConnection):
            raise TypeError(f"Expected ClientConnection, got {type(ws)}")
        self._ws = ws

    async def send_bytes(self, data: bytes) -> None:
        await self._ws.send(data)

    async def send_text(self, data: str) -> None:
        await self._ws.send(data)

    async def receive_bytes(self) -> bytes:
        msg = await self._ws.recv(decode=False)
        if not isinstance(msg, bytes):
            raise TypeError(f"Expected bytes frame, got {type(msg)}")
        return msg

    async def receive_text(self) -> str:
        msg = await self._ws.recv(decode=True)
        if not isinstance(msg, str):
            raise TypeError(f"Expected text frame, got {type(msg)}")
        return msg

    async def receive(self) -> dict:
        msg = await self._ws.recv(decode=None)
        if isinstance(msg, bytes):
            return {"bytes": msg}
        return {"text": msg}
```

### Pattern 3: In-Process ASGI Proxy for One Request

**What:** For each OPEN frame received, create a new httpx request to the local ASGI app, stream the response body back as DATA frames.
**When to use:** Every OPEN frame from relay triggers this pattern.

```python
# Source: verified httpx 0.28.1 docs + ASGITransport
import httpx
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

async def handle_open_frame(
    conn: TunnelConnection,
    request_id: uuid.UUID,
    metadata: dict,
    asgi_client: AsyncClient,  # pre-created, shared across requests
) -> None:
    """Proxy one tunneled request to the local ASGI app."""
    method: str = metadata["method"]
    path: str = metadata["path"]
    query: str = metadata.get("query", "")
    headers: dict = metadata.get("headers", {})
    body_str: str = metadata.get("body", "")
    body: bytes = body_str.encode("latin-1") if body_str else b""

    url = f"http://local{path}"
    if query:
        url = f"{url}?{query}"

    # Build response metadata frame (first DATA frame)
    async with asgi_client.stream(method, url, headers=headers, content=body) as response:
        resp_meta = {
            "status": response.status_code,
            "headers": dict(response.headers),
        }
        await conn.send_data(request_id, json.dumps(resp_meta).encode())
        async for chunk in response.aiter_bytes(chunk_size=65536):
            await conn.send_data(request_id, chunk)

    await conn.send_close(request_id)
```

**CANCEL frame handling:** Before each `send_data`, check if the stream is still open. If the relay sent CANCEL (browser disconnected), `TunnelConnection._dispatch_frame` will have already closed the stream — so catching `StreamNotFoundError` on `send_data` is sufficient to abort cleanly.

### Pattern 4: Relay-Side Mount Code Assignment

**What:** The relay generates the mount code, not the agent. The current `agent_ws.py` requires `?code=...` query param. Phase 10 must change this flow.
**Protocol change needed in `relay/app/routers/agent_ws.py`:**

```python
# Modified agent_ws.py protocol flow:
# 1. Agent connects to ws://relay/agent/ws (NO code param — or optional for reconnect)
# 2. Relay calls generate_mount_code(), registers conn, sends control message
# 3. Agent receives {"type": "mount_registered", "code": "<code>"}
# 4. Agent enters receive loop

@router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    code: str | None = Query(None),  # optional: preferred code for reconnect
) -> None:
    await websocket.accept()
    conn = TunnelConnection(websocket)
    assigned_code = code if code and not get_registry().has_mount(code) else generate_mount_code()
    get_registry().register(assigned_code, conn)
    await conn.send_control({"type": "mount_registered", "code": assigned_code})
    conn.start_heartbeat(HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)
    try:
        await conn.run_receive_loop()
    except WebSocketDisconnect:
        pass
    finally:
        await conn.close()
        try:
            get_registry().deregister(assigned_code)
        except MountNotFoundError:
            pass
```

### Pattern 5: Reconnect Loop with Exponential Backoff

**What:** Auto-reconnect when WebSocket drops, with exponential backoff + jitter.
**When to use:** Outer loop in `agent/connection.py` that wraps the entire connect+register+receive cycle.

```python
# Source: standard backoff algorithm pattern
import asyncio
import random

async def run_agent_loop(
    relay_url: str,
    folder: Path,
    name: str,
) -> None:
    """Outer reconnect loop — runs until Ctrl+C."""
    BASE_DELAY_S: float = 1.0
    CAP_DELAY_S: float = 60.0
    JITTER_RANGE: float = 0.5  # +/- 50% of computed delay

    attempt: int = 0
    last_code: str | None = None

    while True:
        try:
            last_code = await connect_and_serve(relay_url, folder, name, last_code)
            attempt = 0  # reset on clean disconnect
        except Exception:
            attempt += 1
            delay = min(BASE_DELAY_S * (2 ** (attempt - 1)), CAP_DELAY_S)
            jitter = delay * JITTER_RANGE * (random.random() * 2 - 1)
            sleep_for = max(0.0, delay + jitter)
            print_reconnect_status(attempt, sleep_for)
            await asyncio.sleep(sleep_for)
```

### Anti-Patterns to Avoid

- **Spawning uvicorn for the local server:** `create_app()` via `ASGITransport` is zero-overhead. Binding a port creates OS resource usage, random port conflicts, and a network hop.
- **Sharing httpx.AsyncClient across reconnects without closing:** On each new WebSocket connection, create a fresh `AsyncClient`. The old connection's in-flight requests are orphaned on disconnect.
- **Using websockets built-in reconnect iterator for this use case:** `async for websocket in connect(...)` handles reconnect but not "send last mount code on reconnect" — requires manual loop.
- **Blocking `sys.stdin` in Ctrl+C handler:** Use `try/except KeyboardInterrupt` around the outer `asyncio.run()` call. Do cleanup (send disconnect) in the finally block, not a signal handler.
- **Blocking the event loop with print():** All terminal I/O is fine via print() — it's synchronous but fast. Do NOT use `asyncio.to_thread` for print; it adds complexity for no benefit.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| QR code generation | Custom ASCII QR renderer | `generate_ascii_qr()` in `server/app/services/qr_service.py` | Already handles border, box_size, `print_ascii()` |
| WebSocket frame multiplexing | Custom request correlation | `TunnelConnection` from `tunnel/connection.py` | Backpressure, stream lifecycle, heartbeat all handled |
| Binary frame pack/unpack | `struct.pack` by hand | `serialize_frame/deserialize_frame` from `tunnel/frames.py` | Header format, payload length validation, error handling |
| Local server | New HTTP server, open port | `httpx.AsyncClient(transport=ASGITransport(app=create_app()))` | Zero port, zero network hop, reuses entire LAN server |
| Backoff jitter | Custom random distribution | `random.random()` with computed delay (pattern above) | No library needed; full-jitter algorithm is 5 lines |

**Key insight:** Phase 10 is almost entirely plumbing between existing components. The most complex new code is the `WebSocketClientAdapter` shim and the `handle_open_frame` coroutine.

---

## Common Pitfalls

### Pitfall 1: relay agent_ws.py needs protocol change

**What goes wrong:** The current relay endpoint at `/agent/ws?code=...` requires the agent to supply the code. CONTEXT says the relay assigns it. If this endpoint is not modified, the agent cannot implement AGNT-01.
**Why it happens:** Phase 9 implemented a working relay, but the code assignment protocol was finalized in Phase 10 discussion.
**How to avoid:** Modify `agent_ws.py` first (Plan 10-01, Wave 0) before implementing agent logic. Change `code: str = Query(...)` to `code: str | None = Query(None)`. Add `generate_mount_code()` call inside the handler. Send `{"type": "mount_registered", "code": assigned_code}` control message before starting receive loop.
**Warning signs:** Agent connects but has no code to display — `receive_control()` times out or returns wrong type.

### Pitfall 2: httpx is a dev-only dependency

**What goes wrong:** `httpx` is in `[dependency-groups.dev]` in `pyproject.toml`. Production installs (`pip install wifi-ftp-server`) will NOT have httpx. The agent fails with `ModuleNotFoundError`.
**Why it happens:** httpx was added only for tests in earlier phases. STATE.md explicitly notes this.
**How to avoid:** Move `httpx>=0.28.0` from `[dependency-groups.dev]` to `[project.dependencies]` in `pyproject.toml` as the very first change.

### Pitfall 3: WebSocketProtocol adapter receive() shape

**What goes wrong:** `TunnelConnection.run_receive_loop()` calls `self._ws.receive()` expecting `{"bytes": ...}` or `{"text": ...}`. If the adapter's `receive()` returns wrong shape, frames are silently dropped.
**Why it happens:** websockets v16 `recv()` returns `str | bytes` — not a dict.
**How to avoid:** The `WebSocketClientAdapter.receive()` method must inspect the return type of `recv(decode=None)` and wrap in the correct dict key.

### Pitfall 4: CANCEL frame race condition

**What goes wrong:** Browser disconnects mid-download. Relay sends CANCEL frame. Agent is blocked in `send_data()` for the next chunk. `StreamNotFoundError` is raised because `_dispatch_frame` already closed the stream.
**Why it happens:** CANCEL is handled by `TunnelConnection._dispatch_frame` which calls `close_stream()` — this removes the stream from the registry. Subsequent `send_data()` calls then raise `StreamNotFoundError`.
**How to avoid:** In `handle_open_frame`, catch `StreamNotFoundError` from `conn.send_data()` to detect cancelled streams. Break out of the streaming loop cleanly without propagating the exception.

### Pitfall 5: Concurrent request handling

**What goes wrong:** Multiple browser tabs open simultaneously send concurrent OPEN frames. A synchronous `await handle_open_frame(...)` inside the receive loop blocks all other frames.
**Why it happens:** `run_receive_loop()` is a single coroutine — it must not block.
**How to avoid:** For each OPEN frame received, use `asyncio.create_task(handle_open_frame(...))` to dispatch concurrently. The receive loop only calls `conn.open_stream(request_id)` synchronously (to register the stream), then creates a task for the proxy work.

### Pitfall 6: asyncio.run() and KeyboardInterrupt

**What goes wrong:** Pressing Ctrl+C raises `KeyboardInterrupt` inside `asyncio.run()`, which cancels all tasks. The "Unmounting..." cleanup (send disconnect, deregister) is skipped.
**Why it happens:** `asyncio.run()` cancels the main task on `KeyboardInterrupt` before any cleanup runs.
**How to avoid:** Wrap `asyncio.run(run_agent_loop(...))` in a try/except KeyboardInterrupt. The cleanup should be its own coroutine that connects briefly to send a clean deregister message, or use `asyncio.run(graceful_shutdown())` in the except block. Alternatively, trap SIGINT with `loop.add_signal_handler`.

---

## Code Examples

### WebSocket Connection with Mount Code Reception

```python
# Source: websockets v16 docs + tunnel/connection.py patterns
from websockets.asyncio.client import connect
from agent.ws_adapter import WebSocketClientAdapter
from tunnel.connection import TunnelConnection

async def connect_and_serve(
    relay_url: str,
    folder: Path,
    name: str,
    preferred_code: str | None,
) -> str:
    """Connect to relay, receive mount code, serve requests. Returns assigned code."""
    ws_url = f"{relay_url.rstrip('/')}/agent/ws"
    if preferred_code is not None:
        ws_url = f"{ws_url}?code={preferred_code}"

    async with connect(ws_url, ping_interval=None) as raw_ws:
        # ping_interval=None: disable websockets built-in ping; TunnelConnection handles heartbeat
        adapter = WebSocketClientAdapter(raw_ws)
        conn = TunnelConnection(adapter)

        # Receive mount code from relay
        control = await conn.receive_control()
        if control.get("type") != "mount_registered":
            raise ValueError(f"Expected mount_registered, got: {control}")
        assigned_code: str = control["code"]

        conn.start_heartbeat(HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)
        print_mounted(relay_url, assigned_code, folder, name)

        # Set up local ASGI app
        from server.app.config import ServerConfig, set_server_config
        from server.app.main import create_app
        config = ServerConfig(shared_folder=folder, port=0, password_hash=None, read_only=False, receive=False)
        set_server_config(config)
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://local") as asgi_client:
            await run_request_loop(conn, asgi_client)

        return assigned_code
```

### OPEN Frame Dispatch Loop

```python
# Source: tunnel/connection.py + relay/app/routers/mount_proxy.py patterns
import asyncio
import json
import uuid

async def run_request_loop(conn: TunnelConnection, asgi_client: AsyncClient) -> None:
    """Receive OPEN frames and dispatch each as a concurrent task."""
    pending_tasks: set[asyncio.Task] = set()

    async def receive_frames() -> None:
        while True:
            frame_dict = await conn._ws.receive()
            if "bytes" not in frame_dict:
                # text frame — handled by run_receive_loop (pong, etc.)
                continue
            raw = frame_dict["bytes"]
            frame_type, request_id, payload = deserialize_frame(raw)
            if frame_type == FrameType.OPEN:
                metadata = json.loads(payload)
                conn.open_stream(request_id)
                task = asyncio.create_task(
                    handle_open_frame(conn, request_id, metadata, asgi_client)
                )
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)
            else:
                conn._dispatch_frame(frame_type, request_id, payload)
    # NOTE: actual implementation may use run_receive_loop differently;
    # the planner should decide exact loop structure
```

### Exponential Backoff with Full Jitter

```python
# Source: AWS architecture blog full-jitter pattern
import random

def compute_backoff(attempt: int, base: float, cap: float, jitter_factor: float) -> float:
    """Return sleep duration for attempt N using full-jitter exponential backoff.

    Args:
        attempt: 1-based reconnect attempt number.
        base: Initial delay in seconds.
        cap: Maximum delay ceiling in seconds.
        jitter_factor: Fraction of delay to randomize (0.0-1.0).

    Returns:
        Sleep duration in seconds (always >= 0).
    """
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    if base <= 0:
        raise ValueError(f"base must be > 0, got {base}")
    if cap < base:
        raise ValueError(f"cap must be >= base, got cap={cap} base={base}")
    if not 0.0 <= jitter_factor <= 1.0:
        raise ValueError(f"jitter_factor must be in [0, 1], got {jitter_factor}")

    exp_delay = min(base * (2 ** (attempt - 1)), cap)
    jitter = exp_delay * jitter_factor * (random.random() * 2 - 1)
    return max(0.0, exp_delay + jitter)
```

### Terminal Display Functions

```python
# Source: server/app/cli.py print pattern + server/app/services/qr_service.py
from server.app.services.qr_service import generate_ascii_qr

def print_mounted(relay_url: str, code: str, folder: Path, name: str) -> None:
    """Print mount URL, QR code, and status after successful connection."""
    mount_url = f"{relay_url.rstrip('/')}/m/{code}"
    qr = generate_ascii_qr(mount_url)
    print(f"\nMounted: {name}")
    print(f"Sharing: {folder}")
    print(f"Mount code: {code}")
    print(f"Mount URL: {mount_url}")
    print(f"\nScan to access:\n")
    print(qr)
    print("Press Ctrl+C to unmount\n")

def print_request_line(method: str, path: str, status: int) -> None:
    """Print a single access log line. Format: GET /api/files 200"""
    print(f"{method} {path} {status}")

def print_reconnect_status(attempt: int, next_in_s: float) -> None:
    """Print reconnection status line."""
    print(f"Reconnecting (attempt {attempt}, next in {next_in_s:.1f}s)...")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| websockets `websockets.connect()` (legacy sync API) | `websockets.asyncio.client.connect` | websockets v14+ | Must use new async-native API; old import path removed |
| httpx sync client for ASGI tests | `httpx.AsyncClient(transport=ASGITransport(...))` | httpx 0.20+ | Fully async; essential for streaming response bodies without deadlocks |
| `asyncio.get_event_loop()` | `asyncio.run()` for entry point | Python 3.10+ | `asyncio.run()` is the canonical entry point; `get_event_loop()` deprecated for new code |

**Deprecated/outdated:**
- `websockets.connect` (top-level): Removed in websockets v14+; use `websockets.asyncio.client.connect`
- `asyncio.get_event_loop()` for new code: Use `asyncio.run()` at entry point, pass loop references explicitly if needed

---

## Open Questions

1. **agent_ws.py reconnect code semantics — collision handling**
   - What we know: Relay should accept `?code=preferred` and re-register if available
   - What's unclear: If preferred code is occupied (another agent grabbed it), does relay assign new code silently or error? Current `register()` overwrites without checking.
   - Recommendation: `has_mount(code)` check in `agent_ws.py` — if code occupied, generate new code. Send assigned code back in `mount_registered` message. Agent handles new code gracefully.

2. **ServerConfig port=0 for in-process ASGI app**
   - What we know: `ServerConfig` validates `shared_folder` but `port` is stored as-is
   - What's unclear: Whether any part of `create_app()` or its routers use `config.port` at request time
   - Recommendation: Audit `create_app()` and all routers for `get_server_config().port` usage. If none use port at request time (likely — port is only used by uvicorn), pass port=0 safely.

3. **run_request_loop architecture — use run_receive_loop or bypass?**
   - What we know: `TunnelConnection.run_receive_loop()` dispatches DATA/CLOSE/CANCEL to streams but does not expose OPEN frames to callers. The agent needs to intercept OPEN frames.
   - What's unclear: Whether to: (A) add an OPEN-frame callback to `TunnelConnection`, (B) bypass `run_receive_loop()` entirely and call `_ws.receive()` directly, or (C) extend `TunnelConnection` with an `open_handler` hook.
   - Recommendation: Option (A) — add `on_open_frame: Callable | None` callback parameter to `TunnelConnection` or a subclass. Keeps existing relay tests unchanged while enabling agent dispatch. Alternatively, option (B) with a separate receive loop that handles all frame types inline is simpler to test.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + pytest-asyncio 0.25.0 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — asyncio_mode = "auto" |
| Quick run command | `uv run pytest tests/agent/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGNT-01 | `wifi-file-server mount ./files --server <url>` parses correctly | unit | `uv run pytest tests/agent/test_cli.py -x` | ❌ Wave 0 |
| AGNT-01 | `--server` required, `--name` optional with folder default | unit | `uv run pytest tests/agent/test_cli.py::test_mount_args -x` | ❌ Wave 0 |
| AGNT-01 | Existing `wifi-file-server ./files` (LAN mode) still works | unit | `uv run pytest server/tests/test_cli.py -x` | ✅ (existing) |
| AGNT-02 | OPEN frame → httpx ASGI dispatch → DATA+CLOSE frames | unit | `uv run pytest tests/agent/test_proxy.py -x` | ❌ Wave 0 |
| AGNT-02 | CANCEL frame aborts in-flight httpx request | unit | `uv run pytest tests/agent/test_proxy.py::test_cancel -x` | ❌ Wave 0 |
| AGNT-02 | Concurrent OPEN frames handled via asyncio.create_task | unit | `uv run pytest tests/agent/test_proxy.py::test_concurrent -x` | ❌ Wave 0 |
| AGNT-03 | print_mounted() outputs URL, QR code, mount code | unit | `uv run pytest tests/agent/test_display.py -x` | ❌ Wave 0 |
| AGNT-03 | QR code encodes full mount URL | unit | `uv run pytest tests/agent/test_display.py::test_qr_url -x` | ❌ Wave 0 |
| AGNT-04 | compute_backoff() returns values in expected range | unit | `uv run pytest tests/agent/test_connection.py::test_backoff -x` | ❌ Wave 0 |
| AGNT-04 | Reconnect loop retries after WebSocket disconnect | unit | `uv run pytest tests/agent/test_connection.py::test_reconnect -x` | ❌ Wave 0 |
| AGNT-04 | Old code sent as preferred code on reconnect | unit | `uv run pytest tests/agent/test_connection.py::test_reconnect_code -x` | ❌ Wave 0 |
| relay change | agent_ws.py generates code and sends mount_registered | unit | `uv run pytest tests/relay/test_agent_ws.py -x` | ❌ Wave 0 |
| relay change | agent_ws.py accepts preferred code for reconnect | unit | `uv run pytest tests/relay/test_agent_ws.py::test_reconnect_code -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/agent/ tests/relay/test_agent_ws.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/agent/conftest.py` — shared fixtures (MockTunnelConnection variant for agent-side, mock ASGI app)
- [ ] `tests/agent/test_cli.py` — covers AGNT-01
- [ ] `tests/agent/test_proxy.py` — covers AGNT-02
- [ ] `tests/agent/test_display.py` — covers AGNT-03
- [ ] `tests/agent/test_connection.py` — covers AGNT-04
- [ ] `tests/relay/test_agent_ws.py` — covers relay protocol change (mount_registered control message)
- [ ] `agent/__init__.py`, `agent/cli.py`, `agent/connection.py`, `agent/proxy.py`, `agent/display.py` — new package

---

## Sources

### Primary (HIGH confidence)

- `tunnel/connection.py` — TunnelConnection API: `open_stream`, `send_data`, `send_close`, `send_control`, `receive_control`, `run_receive_loop`, `start_heartbeat`
- `tunnel/frames.py` — `serialize_frame`, `deserialize_frame`, frame header format
- `tunnel/protocol.py` — `WebSocketProtocol` structural interface (send_bytes, send_text, receive_bytes, receive_text, receive)
- `relay/app/routers/agent_ws.py` — current relay WebSocket endpoint (requires modification)
- `relay/app/services/mount_registry.py` — `generate_mount_code()`, `register()`, `has_mount()`
- `relay/app/routers/mount_proxy.py` — OPEN frame metadata format (method, path, query, headers, body)
- `server/app/cli.py` — existing argparse pattern, `_build_parser()`
- `server/app/main.py` — `create_app()` factory
- `server/app/services/qr_service.py` — `generate_ascii_qr(url)`
- websockets v16.0 (installed) — `websockets.asyncio.client.connect`, `ClientConnection.send/recv`
- httpx 0.28.1 (installed) — `ASGITransport`, `AsyncClient`, `aiter_bytes`

### Secondary (MEDIUM confidence)

- websockets v16 docs on `ping_interval=None` to disable built-in ping — verified via `connect.__init__` signature inspection
- httpx `ASGITransport` constructor verified via `help(ASGITransport.__init__)` — `app` positional, `raise_app_exceptions`, `root_path`, `client` params

### Tertiary (LOW confidence)

- None for this phase — all claims backed by codebase inspection or installed library verification

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified as installed; API signatures confirmed via Python introspection
- Architecture: HIGH — patterns derived from existing relay/mount_proxy.py which is already working
- Pitfalls: HIGH — most identified via direct code analysis (not hypothesis); relay protocol gap confirmed by reading agent_ws.py

**Research date:** 2026-03-11
**Valid until:** 2026-04-10 (stable libraries; websockets/httpx APIs unlikely to change)
