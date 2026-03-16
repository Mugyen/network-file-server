# Phase 11: Remote Access and Hardening - Research

**Researched:** 2026-03-11
**Domain:** Python async, FastAPI WebSocket proxying, HTTP cookie scoping, TypeScript runtime URL detection
**Confidence:** HIGH

## Summary

Phase 11 closes the last four v1.2 requirements (ACCS-01, ACCS-02, RMUI-01, RMUI-02). Every building block already exists in the codebase — this phase wires them together with minimal new code.

The auth flow (bcrypt + itsdangerous) is fully operational in v1.1 LAN mode. The only changes needed are: (a) extend the CLI parser with `--password` and `--ttl` flags, (b) pass the hashed password to `create_app()` via `ServerConfig`, (c) scope the `Set-Cookie` path to `/m/{code}/` so sessions are mount-isolated, and (d) add a TTL timer that sends a clean disconnect when time expires.

WebSocket tunneling requires adding three new `FrameType` values (`WS_OPEN=0x08`, `WS_DATA=0x09`, `WS_CLOSE=0x0A`) and a parallel bidirectional bridge loop in both the relay's `mount_proxy.py` and the agent's `connection.py`. The relay detects the `Upgrade: websocket` header to distinguish WS from HTTP, then bridges frames. The SPA needs a single module that detects `/m/{code}` from `window.location.pathname` at boot and provides `getApiBase()` and `getWsUrl()` functions used everywhere `API_BASE` and the hardcoded `/ws` URL currently appear.

**Primary recommendation:** Implement in three waves — (1) auth/TTL at the Python layer, (2) WS tunneling at the tunnel/relay/agent layer, (3) SPA URL injection at the client layer. Each wave is independently testable.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Auth enforced agent-side only — relay is fully transparent and auth-unaware
- Reuse existing `--password` flag for mount subcommand — same flag as LAN mode, passed to `create_app()` which already handles bcrypt + itsdangerous
- Cookie path scoped to `/m/{code}/` so different mounts get isolated sessions on the same relay domain
- Login page reuses existing `LoginPage.tsx` identically — no mount-specific adaptations
- Agent-side only TTL — agent tracks its own TTL timer, sends clean disconnect to relay when expired, then exits
- `--ttl` flag accepts human-readable durations: `30m`, `2h`, `1d` — agent parses into seconds
- Terminal shows countdown of remaining time next to mount info, updating periodically: "Expires in 1h 23m"
- Expired mounts show relay's existing error page from Phase 9 (no custom expiry page)
- Runtime URL detection: SPA reads `window.location.pathname` at startup, extracts `/m/{code}` prefix if present
- `API_BASE` becomes dynamic: `/api` in LAN mode, `/m/{code}/api` in remote mode
- Relay strips `/m/{code}` prefix before proxying to agent — agent's ASGI app sees clean `/api/*` paths unchanged
- Static assets served through relay proxy using relative paths in HTML (e.g., `./assets/main.js`)
- Subtle "Remote" pill badge in header, matching existing `[Read Only]` / `[Protected]` badge pattern from Phase 5
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ACCS-01 | Mount owner can set a password via `--password` flag, reusing v1.1 auth at mount level | `--password` flag exists in `_build_parser()` for LAN mode; `_build_mount_parser()` needs the same flag; `hash_password()` + `ServerConfig.password_hash` + `AuthMiddleware` chain already works end-to-end; only changes are CLI flag addition + cookie path scoping |
| ACCS-02 | Mount auto-expires after TTL duration via `--ttl` flag | `--ttl` flag needs to be added to `_build_mount_parser()`; agent needs a duration parser and `asyncio.sleep`-based timer task; on expiry, agent calls `registry.mark_offline()` equivalent (sends clean WS close) then exits; relay already shows `expired.html` for `MountStatus.EXPIRED` |
| RMUI-01 | React SPA detects remote mount context and prefixes API calls with `/m/{code}` | `API_BASE = "/api"` is a single module-level constant in `client.ts`; `uploadWithProgress` hardcodes `/api/` inline; `useWebSocket` hardcodes `/ws`; `main.tsx` probes `/api/files` hardcoded; all 4 call-sites need to use a `getApiBase()` / `getWsUrl()` helper populated from `window.location.pathname` at module load |
| RMUI-02 | Real-time WebSocket features work through relay tunnel | Browser WS to `/m/{code}/ws` must be bridged by relay to agent's `/ws`; requires `WS_OPEN/WS_DATA/WS_CLOSE` frame types in tunnel, a bidirectional bridge coroutine in `mount_proxy.py`, and agent receive loop detecting `WS_OPEN` frames and opening a local WS to the ASGI app |
</phase_requirements>

---

## Standard Stack

### Core (all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bcrypt | >=5.0.0 | Password hashing | Already used in `auth_service.py` |
| itsdangerous | >=2.2.0 | Signed session tokens | Already used in `AuthTokenService` |
| websockets | >=13.0 | Agent tunnel WS client | Already used in `agent/connection.py` |
| httpx + ASGITransport | >=0.28.0 | In-process ASGI dispatch | Already used in `agent/proxy.py` |
| fastapi / starlette | >=0.115.0 | WebSocket server-side | Already used in relay and server |

### No new dependencies needed
All libraries required for Phase 11 are already declared in `pyproject.toml`. The only additions are within-project logic changes.

## Architecture Patterns

### Pattern 1: Cookie Path Scoping for Multi-Tenant Auth

**What:** The `Set-Cookie` response from `POST /api/auth/login` must set `path=/m/{code}/` instead of `path=/` when accessed through the relay. Because the agent handles all auth in-process, the agent's ASGI app issues the cookie. The relay forwards the `Set-Cookie` header verbatim.

**The problem:** `auth.py` currently calls `response.set_cookie(..., path="/")`. When the relay serves multiple mounts on the same domain, a session authenticated for mount `ABC` would also authenticate for mount `XYZ` if both use `path=/`. The browser sends the cookie to both since the cookie path `/` matches all relay URLs.

**The fix:** The agent must know its own mount code so it can scope cookies to `/m/{code}/`. Two approaches are available:

Option A (recommended): Pass the mount code into `connect_and_serve()` / `create_app()` and store it in `ServerConfig`. The auth router reads `get_server_config().mount_code` (a new optional field) and uses it to set the cookie path. In LAN mode, `mount_code=None` → `path="/"` (unchanged behavior).

Option B: Have the relay rewrite the `Set-Cookie` header's `path` attribute. This couples the relay to auth semantics — avoid.

**Cookie isolation example:**
```python
# In auth.py
config = get_server_config()
cookie_path = f"/m/{config.mount_code}/" if config.mount_code is not None else "/"
response.set_cookie(key="session", value=token, httponly=True, samesite="lax", path=cookie_path)
```

**Confidence:** HIGH — cookie `path` attribute is well-specified RFC 6265 behavior. Browsers only send a cookie if the request path starts with the cookie's path.

### Pattern 2: TTL Timer as asyncio Task

**What:** Add a `asyncio.create_task(_ttl_countdown(...))` in `connect_and_serve()` after the mount is registered. The task sleeps until expiry, then cancels the connection.

**Implementation approach:**
```python
async def _ttl_countdown(ttl_seconds: int, conn: TunnelConnection) -> None:
    """Sleep for TTL then close the tunnel connection and exit."""
    await asyncio_sleep(ttl_seconds)
    await conn.close()

# In connect_and_serve(), after receiving mount_registered:
ttl_task = None
if ttl_seconds is not None:
    ttl_task = asyncio.create_task(_ttl_countdown(ttl_seconds, conn))
```

The TTL countdown display uses a separate periodic task (at Claude's discretion, 60s interval is reasonable) that prints remaining time. When the TTL task fires, `conn.close()` causes `_agent_receive_loop_with_metadata` to exit, which returns from `connect_and_serve`. The `run_agent_loop` outer loop must NOT retry when TTL expiry caused the exit — distinguish TTL exit from network drop.

**Signal for "TTL expiry, don't reconnect":** Use a custom exception `MountExpiredError` (distinct from the relay's exception of the same name — define in `agent/exceptions.py`). The TTL task raises it (or `connect_and_serve` detects the expired flag). `run_agent_loop` catches it and breaks instead of retrying.

**Confidence:** HIGH — standard asyncio task + cancellation pattern. Already used in `start_heartbeat`.

### Pattern 3: Human-Readable Duration Parsing

**What:** Parse strings like `30m`, `2h`, `1d` into seconds. This is Claude's discretion — implement in `agent/duration.py`.

```python
import re
from tunnel.enums import FrameType  # example pattern — put in agent/duration.py

_UNITS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_PATTERN = re.compile(r"^(\d+)([smhd])$")

def parse_duration(value: str) -> int:
    """Parse a human-readable duration string into seconds.

    Args:
        value: Duration string, e.g. '30m', '2h', '1d', '90s'.

    Returns:
        Duration in seconds as an integer.

    Raises:
        ValueError: If value does not match pattern ^\d+[smhd]$.
    """
    match = _PATTERN.match(value.strip())
    if match is None:
        raise ValueError(f"Invalid duration '{value}': expected format like '30m', '2h', '1d'")
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * _UNITS[unit]
```

Argparse `type=` parameter calls this during parsing, so invalid TTL strings fail early with a clean error message.

**Confidence:** HIGH — trivial regex; no edge cases for valid inputs.

### Pattern 4: WebSocket Tunneling via New Frame Types

**What:** Browser requests `ws://relay/m/{code}/ws`. Relay detects the WS upgrade, assigns a `ws_id` (UUID), sends a `WS_OPEN` frame to the agent, then bridges frames bidirectionally. Agent opens a local WS to its ASGI app at `/ws?device_name=...` and bridges between the relay tunnel and the local WS.

**New FrameType values (Claude's discretion — these values are available):**
```python
class FrameType(int, Enum):
    OPEN = 0x01
    DATA = 0x02
    CLOSE = 0x03
    CANCEL = 0x04
    ERROR = 0x05
    PING = 0x06
    PONG = 0x07
    WS_OPEN = 0x08   # Relay→Agent: open a WS connection to local /ws
    WS_DATA = 0x09   # Bidirectional: WebSocket message payload
    WS_CLOSE = 0x0A  # Either side: close this WS stream
```

`WS_OPEN` payload format: JSON `{"path": "/ws", "query": "device_name=<name>"}` — relay extracts the query string from the browser's WS URL and includes it so the agent can open `ws://local/ws?device_name=<name>`.

**Relay side — `mount_proxy.py` extension:**

FastAPI's `APIRouter` does not handle WebSocket upgrades with `api_route()`. Add a dedicated `@router.websocket("/m/{code}/{path:path}")` endpoint. Inside:
1. `await websocket.accept()`
2. Look up `conn = get_registry().get_connection(code)` — if raises, close with code 1011
3. Generate `ws_id = uuid.uuid4()`; `conn.open_stream(ws_id)`
4. Send `WS_OPEN` frame to agent with `{"path": f"/{path}", "query": str(websocket.url.query)}`
5. Launch two concurrent tasks: browser→agent pump and agent→browser pump
6. Cancel both tasks on disconnect

**Browser→agent pump:**
```python
async def browser_to_agent() -> None:
    async for message in websocket.iter_text():
        await conn.send_ws_data(ws_id, message.encode("utf-8"))
```

**Agent→browser pump:**
```python
async def agent_to_browser() -> None:
    async for chunk in conn.read_stream_iter(ws_id):
        await websocket.send_text(chunk.decode("utf-8"))
```

**Agent side — receive loop extension in `connection.py`:**

The existing `_agent_receive_loop_with_metadata` already handles `OPEN` frames for HTTP. Add `WS_OPEN` handling:

```python
elif frame_type == FrameType.WS_OPEN:
    metadata = json.loads(payload.decode("utf-8"))
    task = asyncio.create_task(
        handle_ws_open_frame(conn, request_id, metadata, base_url)
    )
```

`handle_ws_open_frame` opens a local WebSocket to the ASGI app using `httpx_ws.aconnect_ws` (already in dev deps as `httpx-ws`) and bridges bidirectionally.

**Note:** `httpx-ws` is currently in dev dependencies. For production use it must move to main dependencies. This was flagged in STATE.md as a pending concern.

**Confidence for WS_OPEN/WS_DATA/WS_CLOSE design:** MEDIUM — the pattern is sound (mirrors how HTTP OPEN/DATA/CLOSE works) but the exact bidirectional bridge implementation in asyncio requires careful task management to avoid race conditions on close.

### Pattern 5: SPA Runtime URL Detection

**What:** A new module `client/src/utils/remoteMount.ts` detects the mount context at module load time and exports `getApiBase()` and `getWsUrl(wsPath)`.

```typescript
// client/src/utils/remoteMount.ts

/**
 * Extract the remote mount prefix from the current URL path, if any.
 * Returns "/m/{code}" when running through the relay, or "" in LAN mode.
 */
function detectMountPrefix(): string {
  const match = /^(\/m\/[^/]+)/.exec(window.location.pathname);
  return match !== null ? match[1] : "";
}

/** Module-level constant — computed once at boot. */
const MOUNT_PREFIX: string = detectMountPrefix();

/** Return the API base path for the current context. */
export function getApiBase(): string {
  return MOUNT_PREFIX === "" ? "/api" : `${MOUNT_PREFIX}/api`;
}

/** Return true if the SPA is running through the relay. */
export function isRemoteMount(): boolean {
  return MOUNT_PREFIX !== "";
}

/** Return the mount prefix (e.g. "/m/ABC12345") or "" in LAN mode. */
export function getMountPrefix(): string {
  return MOUNT_PREFIX;
}

/** Return the WebSocket URL for the given WS path (e.g. "/ws"). */
export function getWsUrl(wsPath: string, queryString: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const base = `${protocol}//${window.location.host}`;
  const path = MOUNT_PREFIX === "" ? wsPath : `${MOUNT_PREFIX}${wsPath}`;
  return `${base}${path}?${queryString}`;
}
```

**Call sites that need updating:**
1. `client/src/api/client.ts`: `const API_BASE = "/api"` → `const API_BASE = getApiBase()`
2. `client/src/api/client.ts`: `uploadWithProgress()` — inline `/api/` hardcode → use `getApiBase()`
3. `client/src/hooks/useWebSocket.ts`: WS URL construction → use `getWsUrl("/ws", ...)`
4. `client/src/main.tsx`: probe fetch `"/api/files"` → use `getApiBase()`

**Remote badge in `ModeBadges.tsx`:**
```tsx
interface ModeBadgesProps {
  readOnly: boolean;
  passwordProtected: boolean;
  remote: boolean;  // new
}
// Add "Remote" pill badge using same styling pattern as existing badges
```

`App.tsx` passes `remote={isRemoteMount()}` to `<ModeBadges>`.

**Confidence:** HIGH — `window.location.pathname` is standard browser API; regex `/^(\/m\/[^/]+)/` handles all valid mount codes (8-char URL-safe base64).

### Anti-Patterns to Avoid

- **Relay cookie rewriting:** Do not have the relay rewrite `Set-Cookie` path headers. Auth is agent-side — let the agent control its own cookie scope.
- **Global `API_BASE` mutation:** Do not use a mutable module-level variable that gets reassigned. Use a function `getApiBase()` computed once from `window.location` at module load.
- **WS frames sharing HTTP stream IDs:** Do not reuse HTTP request IDs for WS connections. Use separate UUID namespace per WS session.
- **TTL retry in `run_agent_loop`:** When TTL expires, `run_agent_loop` MUST NOT retry. Use a typed exception to distinguish TTL exit from network disconnect.
- **`path="/"` for remote mount cookies:** Without path scoping, one authenticated mount session leaks to all other mounts on the relay domain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Duration parsing | Custom parser | Simple `re.compile` + dict lookup (3 lines) | No library needed; the valid set is `[smhd]` only |
| WS client in agent | Raw websockets | `httpx-ws` `aconnect_ws` | Already in dev deps; provides ASGI-compatible WS client |
| Cookie signing | Custom HMAC | `itsdangerous.URLSafeTimedSerializer` (already used) | Tamper-evident, time-limited tokens |
| Password hashing | Plain SHA-256 | `bcrypt` (already used) | Constant-time comparison, work factor |

## Common Pitfalls

### Pitfall 1: Cookie Path Not Scoped — Cross-Mount Session Leak
**What goes wrong:** Agent sets `Set-Cookie: session=...; path=/`. Browser sends the cookie to `/m/OTHER_CODE/api/*` on the same relay domain. Remote user is authenticated on a mount they didn't log into.
**Why it happens:** Default cookie path is the directory of the login endpoint, not `/`.
**How to avoid:** Store `mount_code` in `ServerConfig`. Auth router checks `mount_code` and sets `path=/m/{mount_code}/` for remote mounts, `path=/` for LAN.
**Warning signs:** Test: login to mount A, fetch `/m/B/api/files` from same browser — should get 401.

### Pitfall 2: TTL Disconnect Triggers Reconnect Loop
**What goes wrong:** `run_agent_loop` retries on any exception from `connect_and_serve`. If the TTL task raises a generic exception (or `conn.close()` causes `ConnectionError`), the agent reconnects with a new mount code and runs forever.
**Why it happens:** TTL expiry and network drops are currently indistinguishable.
**How to avoid:** Define `AgentExpiredError` in `agent/exceptions.py`. The TTL task sets a flag that `connect_and_serve` checks after the receive loop exits; if TTL-caused, raise `AgentExpiredError`. `run_agent_loop` catches `AgentExpiredError` and breaks.
**Warning signs:** Agent terminal restarts after TTL instead of printing "Mount expired".

### Pitfall 3: WS Bridge Task Leak on Browser Disconnect
**What goes wrong:** Browser closes its WS connection. Relay-side `browser_to_agent` task exits. But `agent_to_browser` task is still blocking on `conn.read_stream_iter`. Stream stays open on the agent side consuming a slot in `MAX_STREAMS=100`.
**Why it happens:** The two pump tasks are independent; one completing doesn't cancel the other.
**How to avoid:** Wrap both pump tasks with `asyncio.gather(..., return_exceptions=True)` and cancel both in a `finally` block. Send `WS_CLOSE` frame to agent on browser disconnect.
**Warning signs:** `MAX_STREAMS` exhaustion under browser tab cycling; streams stuck open.

### Pitfall 4: Vite Dev Proxy Not Covering `/m/` Paths
**What goes wrong:** During development, Vite's proxy config covers `/api` and `/ws` but not `/m/{code}/*`. Running against a remote relay during dev requires the relay URL as `--server` argument; the Vite proxy is irrelevant for that. However, if a developer tries to test the SPA locally against a relay, assets won't load via the relay unless `<base href>` or relative paths are used.
**Why it happens:** Vite proxy only covers listed paths.
**How to avoid:** Ensure HTML uses relative asset paths (Vite default `base: "/"` outputs `./assets/...` in built HTML, which resolves relative to the page URL). The SPA is served from `/m/{code}/` so `./assets/main.js` resolves to `/m/{code}/assets/main.js` — which the relay proxies to the agent which serves it from `/assets/main.js` via `StaticFiles`.
**Warning signs:** 404 on `/m/{code}/assets/main.js`; check that agent's `create_app()` mounts `/assets` statically.

### Pitfall 5: `httpx-ws` in Dev-Only Dependencies
**What goes wrong:** Production agent build fails because `httpx-ws` is listed under `[dependency-groups] dev` only.
**Why it happens:** `httpx-ws` is needed at runtime in the agent for in-process WS bridging, not just tests.
**How to avoid:** Move `httpx-ws>=0.8.2` from `[dependency-groups] dev` to `[project] dependencies` in `pyproject.toml`.
**Warning signs:** `ImportError: No module named 'httpx_ws'` in production install.

### Pitfall 6: SPA Auth Probe Uses Hardcoded `/api/files`
**What goes wrong:** `main.tsx` probes `fetch("/api/files", { credentials: "include" })` to test if the session cookie is still valid. In remote mode this should be `fetch("/m/{code}/api/files", ...)`.
**Why it happens:** The probe in `main.tsx` was written before remote mode existed.
**How to avoid:** Replace hardcoded `/api/files` with `${getApiBase()}/files` using the new `remoteMount.ts` utility.

## Code Examples

### Adding `--password` and `--ttl` to Mount Parser
```python
# In server/app/cli.py — _build_mount_parser()
parser.add_argument(
    "--password",
    type=str,
    help="Password to protect the remote mount (max 72 bytes)",
)
parser.add_argument(
    "--ttl",
    type=parse_duration,  # from agent.duration
    dest="ttl_seconds",
    help="Auto-expire duration (e.g. 30m, 2h, 1d)",
)
```

### Extending ServerConfig with mount_code
```python
# server/app/config.py
class ServerConfig:
    shared_folder: Path
    port: int
    password_hash: bytes | None
    read_only: bool
    receive: bool
    mount_code: str | None  # None in LAN mode; set by agent for remote mounts

    def __init__(
        self,
        shared_folder: Path,
        port: int,
        password_hash: bytes | None,
        read_only: bool,
        receive: bool,
        mount_code: str | None,
    ) -> None: ...
```

### connect_and_serve Signature Extension
```python
async def connect_and_serve(
    relay_url: str,
    folder: Path,
    name: str,
    preferred_code: str | None,
    password_hash: bytes | None,
    ttl_seconds: int | None,
) -> str:
    ...
    config = ServerConfig(
        shared_folder=folder,
        port=0,
        password_hash=password_hash,
        read_only=False,
        receive=False,
        mount_code=assigned_code,
    )
```

### TTL Countdown Display (Claude's discretion — 60s interval)
```python
async def _print_ttl_countdown(ttl_seconds: int) -> None:
    """Print remaining TTL to terminal every 60 seconds."""
    import time
    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        remaining = ttl_seconds - int(elapsed)
        if remaining <= 0:
            return
        hours, rem = divmod(remaining, 3600)
        minutes = rem // 60
        if hours > 0:
            print(f"Expires in {hours}h {minutes}m")
        else:
            print(f"Expires in {minutes}m")
        await asyncio_sleep(60)
```

### WS Bridge in mount_proxy.py
```python
@router.websocket("/m/{code}/{path:path}")
async def proxy_websocket(websocket: WebSocket, code: str, path: str) -> None:
    try:
        conn = get_registry().get_connection(code)
    except (MountNotFoundError, MountOfflineError, MountExpiredError):
        await websocket.close(code=1011)
        return

    await websocket.accept()
    ws_id = uuid.uuid4()
    conn.open_stream(ws_id)

    metadata = {"path": f"/{path}", "query": str(websocket.url.query)}
    await conn.send_ws_open(ws_id, metadata)

    async def browser_to_agent() -> None:
        try:
            async for message in websocket.iter_text():
                await conn.send_ws_data(ws_id, message.encode("utf-8"))
        except Exception:
            pass

    async def agent_to_browser() -> None:
        try:
            async for chunk in conn.read_stream_iter(ws_id):
                await websocket.send_text(chunk.decode("utf-8"))
        except Exception:
            pass

    tasks = [
        asyncio.create_task(browser_to_agent()),
        asyncio.create_task(agent_to_browser()),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await conn.send_ws_close(ws_id)
        except Exception:
            pass
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `path="/"` cookie for all auth | `path=/m/{code}/` for remote mounts | Phase 11 | Prevents cross-mount session leak |
| Hardcoded `API_BASE = "/api"` | `getApiBase()` from `remoteMount.ts` | Phase 11 | SPA works in both LAN and relay contexts |
| No TTL on mounts | `--ttl` flag with agent-side timer | Phase 11 | Mounts auto-expire without manual intervention |
| HTTP-only tunnel | HTTP + WS frame types in tunnel | Phase 11 | All real-time features work through relay |

## Open Questions

1. **Binary WS messages from the browser**
   - What we know: The app's WebSocket protocol uses JSON text messages exclusively (`websocket.receive_json()` in `websocket.py`)
   - What's unclear: If any future feature sends binary WS frames, the current `iter_text()` bridge would drop them
   - Recommendation: Use `iter_bytes()` in the bridge and dispatch on frame type, or document text-only assumption with a comment. For this phase, text-only is sufficient.

2. **`httpx-ws` for in-process WS in agent**
   - What we know: `httpx-ws` is used in tests (`ASGIWebSocketTransport`) and works for in-process WS
   - What's unclear: Whether `aconnect_ws` with `ASGIWebSocketTransport` works correctly for long-lived bidirectional WS sessions (not just request/response)
   - Recommendation: Test explicitly — the existing `test_agent_connection.py` pattern shows how to use it; verify that the transport does not impose a request/response lifecycle limit

3. **Relay WS endpoint route conflict with HTTP proxy route**
   - What we know: `mount_proxy.py` has `@router.api_route("/m/{code}/{path:path}", methods=["GET","POST",...])` — this catches all HTTP verbs but NOT WS upgrades
   - What's unclear: Whether FastAPI/Starlette routes a WS upgrade to `api_route` or requires a separate `@router.websocket()` endpoint
   - Recommendation: Use `@router.websocket("/m/{code}/{path:path}")` as a separate decorator — Starlette routes WS upgrades to `@websocket` handlers, not `@api_route`. They can coexist on the same path pattern.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.0 + pytest-asyncio 0.25.0 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ server/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACCS-01 | `--password` flag parsed by mount parser | unit | `uv run pytest tests/agent/test_cli.py -x -k password` | ✅ (test_cli.py exists; add test) |
| ACCS-01 | `ServerConfig` carries `mount_code`; auth cookie path scoped | unit | `uv run pytest server/tests/ -x -k mount_code` | ❌ Wave 0 |
| ACCS-01 | Remote login sets cookie with `path=/m/{code}/` | integration | `uv run pytest tests/agent/ -x -k cookie_path` | ❌ Wave 0 |
| ACCS-02 | `--ttl` flag parsed and converted to seconds | unit | `uv run pytest tests/agent/test_cli.py -x -k ttl` | ✅ (add test) |
| ACCS-02 | TTL timer fires `conn.close()` after duration | unit | `uv run pytest tests/agent/test_agent_connection.py -x -k ttl` | ✅ (add test) |
| ACCS-02 | `run_agent_loop` does NOT retry after TTL expiry | unit | `uv run pytest tests/agent/test_agent_connection.py -x -k expired` | ✅ (add test) |
| RMUI-01 | `detectMountPrefix` returns `""` for `/` | unit (vitest) | `cd client && npx vitest run src/utils/remoteMount` | ❌ Wave 0 |
| RMUI-01 | `detectMountPrefix` returns `/m/ABC12345` for `/m/ABC12345/` | unit (vitest) | `cd client && npx vitest run src/utils/remoteMount` | ❌ Wave 0 |
| RMUI-01 | `getApiBase()` returns `/m/{code}/api` in remote context | unit (vitest) | `cd client && npx vitest run src/utils/remoteMount` | ❌ Wave 0 |
| RMUI-02 | Relay WS endpoint accepts upgrade, sends `WS_OPEN` frame | integration | `uv run pytest tests/relay/test_mount_proxy.py -x -k websocket` | ✅ (add test) |
| RMUI-02 | Agent receive loop handles `WS_OPEN` frame, opens local WS | integration | `uv run pytest tests/agent/test_agent_connection.py -x -k ws_open` | ✅ (add test) |
| RMUI-02 | WS bridge forwards text messages bidirectionally | integration | `uv run pytest tests/agent/ tests/relay/ -x -k ws_bridge` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ server/tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ server/tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_config.py` — add test for `ServerConfig` with `mount_code` field
- [ ] `server/tests/test_auth_router.py` — add test for cookie path scoped to `/m/{code}/`
- [ ] `client/src/utils/remoteMount.test.ts` — unit tests for `detectMountPrefix`, `getApiBase`, `getWsUrl`
- [ ] `tests/agent/test_duration.py` — unit tests for `parse_duration` (valid and invalid inputs)
- [ ] `tests/agent/test_ws_bridge.py` — integration test for WS frame bridging through tunnel
- [ ] `client/vitest.config.ts` — vitest config if not already present (check `client/package.json`)

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection:
  - `tunnel/enums.py` — existing `FrameType` values (0x01–0x07); 0x08–0x0A are available
  - `tunnel/frames.py` + `tunnel/constants.py` — wire format: `>B16sI` = 1+16+4 = 21-byte header
  - `server/app/middleware/auth_middleware.py` — cookie extraction logic; `samesite="lax"`, `path="/"`
  - `server/app/routers/auth.py` — `set_cookie(..., path="/")` — confirmed needs scoping
  - `server/app/config.py` — `ServerConfig` fields; no `mount_code` yet
  - `agent/connection.py` — `connect_and_serve` signature; `ServerConfig` construction
  - `client/src/api/client.ts` — `API_BASE = "/api"` constant; inline `/api/` in `uploadWithProgress`
  - `client/src/hooks/useWebSocket.ts` — hardcoded `/ws` URL
  - `client/src/main.tsx` — hardcoded `"/api/files"` probe
  - `relay/app/routers/mount_proxy.py` — HTTP-only `api_route`; no WS handling
  - `relay/app/services/mount_registry.py` — `MountStatus.EXPIRED` already defined
  - `pyproject.toml` — `httpx-ws` is in dev deps only

### Secondary (MEDIUM confidence)
- RFC 6265 (HTTP State Management) — `path` attribute semantics for `Set-Cookie`; browsers restrict cookie sending to paths that start with the cookie's `path` attribute
- FastAPI/Starlette WebSocket routing — `@router.websocket()` decorator is separate from `@router.api_route()` and is required for WS upgrade handling

### Tertiary (LOW confidence)
- `httpx-ws` `aconnect_ws` behavior for long-lived bidirectional sessions via `ASGIWebSocketTransport` — needs empirical validation in test

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new dependencies
- Architecture (auth/TTL): HIGH — follows established project patterns exactly
- Architecture (WS tunneling): MEDIUM — bidirectional async bridge has known task-leak pitfall; needs careful implementation
- Architecture (SPA URL detection): HIGH — trivial regex on stable browser API
- Pitfalls: HIGH — identified from code inspection of actual current behavior

**Research date:** 2026-03-11
**Valid until:** 2026-04-10 (stable codebase; no fast-moving dependencies)
