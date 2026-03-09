# Architecture Patterns

**Domain:** WiFi File Server v1.1 -- Access Control, Sharing Modes, Device Discovery, Terminal UI, Speed Test
**Researched:** 2026-03-10

## Existing Architecture Summary

The current v1.0 system follows a clean layered architecture:

```
CLI (cli.py)
  -> ServerConfig (config.py) -- global module-level singleton
  -> FastAPI App (main.py) -- create_app() factory
       -> Routers: files, clipboard, file_requests, server_info, websocket
       -> Services: file_service, clipboard_service, file_request_service,
                    connection_manager, network_service, qr_service, persistence
       -> Models: enums.py, schemas.py (Pydantic)
       -> Exceptions: PathTraversalError, FileConflictError, InvalidFileNameError

React SPA (client/)
  -> App.tsx -- monolith component, all state via hooks
  -> hooks/ -- useWebSocket, useUpload, useClipboard, useFileRequests, etc.
  -> api/ -- client.ts (apiFetch/apiPost/apiPatch/apiDelete + XHR upload)
  -> components/ -- 25 components, flat structure + preview/ subdirectory
  -> types/ -- files.ts, websocket.ts, clipboard.ts, fileRequests.ts, etc.
```

Key architectural properties:
- **No database** -- clipboard persisted via JSON file, file requests in-memory
- **Global config singleton** -- `get_server_config()` returns module-level `_config`
- **Single WebSocket endpoint** `/ws` -- multiplexed via `type` field in JSON messages
- **ConnectionManager** -- tracks `active_connections: dict[str, WebSocket]` and `device_names: dict[str, str]`
- **CORS wildcard** -- `allow_origins=["*"]` for LAN access, no credentials
- **SPA catch-all** -- `/{path:path}` route serves `index.html` for non-API, non-asset paths

## How Each Feature Integrates

### 1. Password Protection

**Integration point:** FastAPI middleware layer, between CORS and router dispatch.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/middleware/auth.py` | Backend | NEW file | Middleware checking session cookie on every request |
| `server/app/routers/auth.py` | Backend | NEW file | `POST /api/auth/login` and `POST /api/auth/logout` |
| `server/app/services/auth_service.py` | Backend | NEW file | Password verification, session token generation/validation |
| `client/src/components/LoginPage.tsx` | Frontend | NEW file | Password entry form |
| `client/src/hooks/useAuth.ts` | Frontend | NEW file | Auth state management, session check |
| `client/src/api/auth.ts` | Frontend | NEW file | Login/logout API calls |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/config.py` | Add `password_hash: str \| None` field to `ServerConfig` |
| `server/app/cli.py` | Add `--password` CLI argument, hash with bcrypt before storing |
| `server/app/main.py` | Add auth middleware in `create_app()` |
| `client/src/App.tsx` | Wrap content in auth gate -- show LoginPage when 401 |
| `client/src/api/client.ts` | Handle 401 responses globally (trigger login state) |

**Data flow:**

```
1. CLI: --password "secret" -> bcrypt.hash("secret") -> ServerConfig.password_hash
2. Request arrives -> AuthMiddleware checks:
   a. password_hash is None? -> pass through (no auth configured)
   b. Path is /api/auth/* or /s/*? -> pass through (login + share links)
   c. Has valid session cookie? -> pass through
   d. Otherwise -> 401
3. POST /api/auth/login: {password} -> bcrypt.verify(password, hash) -> set signed cookie
4. Cookie: itsdangerous URLSafeTimedSerializer signs {authenticated: true} -> HttpOnly cookie
```

**Architecture decision -- itsdangerous over JWT:** For a single shared password (no user identity to encode), itsdangerous `URLSafeTimedSerializer` is simpler than JWT. It handles signing + timestamp-based expiry in one call. No PyJWT dependency needed. itsdangerous is already a transitive dependency of Starlette's SessionMiddleware.

**Architecture decision -- middleware over per-route dependency:** A middleware intercepts ALL requests including static files and the SPA catch-all. A `Depends(require_auth)` approach would require adding the dependency to every router, which is error-prone (one missed route = security hole). Middleware with an explicit allowlist of unauthenticated paths is the correct pattern for a server-wide gate.

**CORS interaction (CRITICAL):** Password protection via cookies requires `allow_credentials=True` in CORS, which is mutually exclusive with `allow_origins=["*"]`. Since the SPA is served from the same origin in production (FastAPI serves built React), CORS is not involved for same-origin requests. The existing wildcard CORS config is only needed for development (Vite dev server on different port). In dev mode with auth enabled, set origin explicitly to `http://localhost:5173` and add `allow_credentials=True`. This is the most subtle integration detail in the entire v1.1 plan.

**WebSocket auth:** Browsers send cookies (but not custom headers) with WebSocket upgrade requests. The auth middleware validates the session cookie on WS upgrades automatically since it intercepts before the route handler.

### 2. Read-Only Mode

**Integration point:** Middleware layer, blocking write operations.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/middleware/read_only.py` | Backend | NEW file | Middleware rejecting write operations |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/config.py` | Add `read_only: bool` field to `ServerConfig` |
| `server/app/cli.py` | Add `--read-only` CLI flag |
| `server/app/main.py` | Add read-only middleware |
| `server/app/models/schemas.py` | Add `read_only: bool` to `ServerInfo` |
| `server/app/routers/server_info.py` | Return `read_only` from config in response |
| `client/src/types/serverInfo.ts` | Add `read_only: boolean` |
| `client/src/App.tsx` | Conditionally hide upload/delete/rename/create-folder UI |

**Architecture decision -- middleware over per-route checks:** A middleware checking HTTP method + path is cleaner than adding `if config.read_only: raise 403` to every write endpoint. The middleware intercepts:

```
Blocked when read_only=True:
  POST   /api/files/upload
  DELETE /api/files
  PATCH  /api/files/rename
  POST   /api/folders
  POST   /api/clipboard/
  PATCH  /api/clipboard/{id}
  DELETE /api/clipboard/{id}
  POST   /api/file-requests/
  POST   /api/file-requests/{id}/fulfill

Allowed always (reads):
  GET    /api/files
  GET    /api/files/download
  GET    /api/files/preview
  GET    /api/files/search
  POST   /api/files/download-zip  (POST but read-only semantics)
  GET    /api/server-info
  GET    /api/clipboard/
  GET    /api/file-requests/
  WS     /ws
```

**Frontend integration:** The `/api/server-info` response already flows to App.tsx via `fetchServerInfo()`. Adding `read_only: boolean` to this response lets the frontend conditionally render write UI. Backend middleware is the enforcement layer; frontend hiding is UX polish.

### 3. Receive Mode / Drop Box

**Integration point:** Parallel UI mode with separate entry point and stripped-down interface.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/routers/dropbox.py` | Backend | NEW file | `POST /api/dropbox/upload`, `GET /api/dropbox/config` |
| `server/app/services/dropbox_service.py` | Backend | NEW file | Drop box config, upload folder management |
| `client/src/drop-main.tsx` | Frontend | NEW file | Separate entry point for drop box SPA |
| `client/src/DropBox.tsx` | Frontend | NEW file | Root component for drop box interface |
| `client/src/components/dropbox/DropZone.tsx` | Frontend | NEW file | Upload-only drag-and-drop area |
| `client/src/components/dropbox/UploadConfirmation.tsx` | Frontend | NEW file | Thank-you message after upload |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/cli.py` | Add `--receive` CLI flag |
| `server/app/config.py` | Add `receive_mode: bool`, `receive_message: str` |
| `server/app/main.py` | Mount drop box route, serve `drop.html` at `/drop` |
| `client/vite.config.ts` | Add multi-page entry for `drop.html` |

**Architecture decision -- separate entry point, not a mode in App.tsx:** The drop box UI is fundamentally different from the file browser. It shows ONLY an upload zone, a welcome message, and confirmation. Embedding this as a conditional branch in App.tsx (already 500 lines) would bloat the main component and couple unrelated concerns.

1. Backend serves `/drop` route that renders `drop.html`
2. Vite builds a second entry via `client/src/drop-main.tsx`
3. Drop box is a lightweight standalone React app with its own minimal component tree
4. Shared code (api client, upload with XHR progress) is imported from existing modules

**Upload destination:** Drop box uploads go to `_received/` within the shared folder, organized by timestamp subfolder. The `dropbox_service` creates `_received/{YYYY-MM-DD_HH-MM}/` directories.

**Data flow:**

```
1. Server starts with --receive -> config.receive_mode = True
2. Client visits /drop -> served drop.html -> renders DropBox app
3. User drops files -> POST /api/dropbox/upload (reuses XHR upload pattern)
4. Backend: dropbox_service saves to _received/{timestamp}/
5. WebSocket broadcast: "New drop box upload from {device_name}"
```

**Interaction with password protection:** If both `--password` and `--receive` are set, the drop box page requires authentication too. The auth middleware applies uniformly. This is intentional -- if you password-protected the server, you probably do not want anonymous uploads either.

### 4. Expiring Share Links

**Integration point:** New token-based route bypassing normal file access.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/routers/share.py` | Backend | NEW file | `POST /api/share/create`, `GET /s/{token}` |
| `server/app/services/share_service.py` | Backend | NEW file | Token generation/validation via itsdangerous |
| `client/src/components/ShareDialog.tsx` | Frontend | NEW file | Dialog to create share link with expiry |
| `client/src/api/share.ts` | Frontend | NEW file | Create share link API |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/main.py` | Include share router; register `/s/{token}` BEFORE SPA catch-all |
| `server/app/models/enums.py` | Add `ShareLinkExpiry` enum (1h, 6h, 24h, 7d) |
| `client/src/components/FileRow.tsx` | Add "Share" action button |

**Token architecture using itsdangerous:**

```python
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

serializer = URLSafeTimedSerializer(secret_key)

# Create: encode file path + max_age into signed token
token = serializer.dumps({"path": "docs/report.pdf", "max_age": 3600})

# Validate: unsign + check embedded timestamp vs max_age
try:
    data = serializer.loads(token, max_age=3600)
except SignatureExpired:
    # Token is older than max_age
    raise HTTPException(status_code=410, detail="Link has expired")
except BadSignature:
    raise HTTPException(status_code=403, detail="Invalid link")
```

**Architecture decision -- stateless tokens over in-memory store:** Since we have no database, tokens are self-contained. The file path and expiry duration are encoded in the signed token. The server validates the signature and checks the embedded timestamp. No server-side storage needed. Tradeoff: tokens cannot be revoked before expiry. For a LAN tool with 1h-7d lifetimes, this is acceptable.

**Route placement (CRITICAL):** The `/s/{token}` route MUST be registered BEFORE the SPA catch-all `/{path:path}` in `main.py`. FastAPI matches routes in registration order. If the catch-all is first, `/s/...` requests serve `index.html` instead of triggering the file download. Currently the SPA catch-all is registered via `@application.get("/{path:path}")` inside `create_app()`. The share router must be included before this registration.

**Auth bypass:** Share links work WITHOUT authentication. The auth middleware must exclude `/s/*` paths. The token IS the authentication for that specific file.

### 5. Device Discovery

**Integration point:** Extends existing ConnectionManager + new mDNS service.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/services/device_service.py` | Backend | NEW file | Device tracking, User-Agent parsing |
| `server/app/services/mdns_service.py` | Backend | NEW file | mDNS/Bonjour via python-zeroconf |
| `server/app/routers/devices.py` | Backend | NEW file | `GET /api/devices` endpoint |
| `client/src/components/DevicePanel.tsx` | Frontend | NEW file | Connected devices list |
| `client/src/hooks/useDevices.ts` | Frontend | NEW file | Device list state |
| `client/src/api/devices.ts` | Frontend | NEW file | Fetch devices API |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/services/connection_manager.py` | Add User-Agent, IP, timestamp storage per device |
| `server/app/routers/websocket.py` | Pass request headers/scope to ConnectionManager on connect |
| `server/app/models/enums.py` | Add `DeviceType` enum, `WSMessageType.DEVICE_LIST_UPDATED` |
| `client/src/App.tsx` | Add DevicePanel toggle in header |
| `client/src/types/websocket.ts` | Add `DEVICE_LIST_UPDATED` message type |

**ConnectionManager extension:**

```python
# Current state:
active_connections: dict[str, WebSocket]  # device_id -> ws
device_names: dict[str, str]              # device_id -> name

# Extended to include:
device_info: dict[str, DeviceInfo]        # device_id -> full info
```

Where `DeviceInfo` holds: `device_id`, `device_name`, `device_type` (from User-Agent), `ip_address` (from WebSocket scope), `connected_at`, `user_agent`.

**User-Agent parsing:** Lightweight regex, not a full library:
- "iPhone" or "iPad" -> PHONE / TABLET
- "Android" + "Mobile" -> PHONE
- "Android" without "Mobile" -> TABLET
- "Macintosh" or "Windows" or "Linux" -> DESKTOP
- Fallback -> UNKNOWN

**mDNS broadcast:** `python-zeroconf` registers the server as `_wififileserver._tcp.local.` so it appears in network service browsers. Registration at startup, unregistration at shutdown. Runs in its own background thread (zeroconf manages its event loop internally).

```python
from zeroconf import ServiceInfo, Zeroconf
info = ServiceInfo(
    "_wififileserver._tcp.local.",
    "WiFi File Server._wififileserver._tcp.local.",
    addresses=[socket.inet_aton(ip)],
    port=port,
    properties={"path": "/"},
)
zeroconf = Zeroconf()
zeroconf.register_service(info)
```

**Real-time updates:** On connect/disconnect, broadcast the full device list to all clients via `DEVICE_LIST_UPDATED` WebSocket message. Frontend `useDevices` hook updates accordingly.

### 6. Terminal UI

**Integration point:** Replaces `print()` calls in `cli.py` with a Rich Live display.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/services/terminal_ui.py` | Backend | NEW file | Rich-based terminal dashboard |
| `server/app/services/stats_collector.py` | Backend | NEW file | Thread-safe server metrics aggregation |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/cli.py` | Replace `print()` with terminal UI; add `--no-tui` for plain output |
| `server/app/main.py` | Add lifespan event to start/stop terminal UI |
| `server/app/routers/files.py` | Report upload/download events to stats_collector |
| `server/app/services/connection_manager.py` | Report connect/disconnect to stats_collector |

**Architecture decision -- Rich over Textual:** Textual is a full TUI framework for interactive terminal apps. The WiFi File Server terminal is a read-only dashboard -- it displays information but the user does not interact beyond Ctrl+C. Rich's `Live` display is the right tool: it updates a rendered Layout in-place without requiring an event loop takeover.

**Terminal dashboard layout:**

```
+---------------------------------------------------+
| WiFi File Server v1.1                             |
+---------------------------------------------------+
| URL: http://192.168.1.5:8000    Devices: 3        |
| QR: [ascii QR code]                               |
+---------------------------------------------------+
| Connected Devices              | Stats             |
| - Swift Fox (iPhone, 1m ago)   | Uploads: 12       |
| - Brave Owl (MacBook, 5m ago)  | Downloads: 34     |
| - Keen Hawk (Windows, 2m ago)  | Bandwidth: 1.2 GB |
+---------------------------------------------------+
| Recent Activity                                   |
| [12:01] Swift Fox uploaded photo.jpg (2.3 MB)     |
| [12:00] Brave Owl downloaded report.pdf (1.1 MB)  |
| [11:58] Keen Hawk connected                       |
+---------------------------------------------------+
```

**StatsCollector pattern:** Thread-safe singleton with `threading.Lock`. Routers call `stats_collector.record_upload(filename, size)` etc. Terminal UI polls at 1-second intervals via Rich Live refresh.

**uvicorn log integration:** When TUI is active, uvicorn access logs must be suppressed to avoid corrupting the Rich display. Set `uvicorn.run(log_level="warning")` when TUI is active, route access events through `stats_collector` instead.

**Architecture decision -- no async in terminal UI:** Rich's `Live` uses a background thread. StatsCollector uses `threading.Lock`. This avoids coupling the TUI to asyncio. The separation is clean: async request handlers write to StatsCollector, synchronous TUI thread reads from it.

### 7. Speed Test

**Integration point:** New API endpoint + frontend component for bandwidth measurement.

**New components:**

| Component | Layer | Type | Purpose |
|-----------|-------|------|---------|
| `server/app/routers/speedtest.py` | Backend | NEW file | `GET /api/speedtest/download`, `POST /api/speedtest/upload` |
| `client/src/components/SpeedTest.tsx` | Frontend | NEW file | Speed test UI with progress |
| `client/src/hooks/useSpeedTest.ts` | Frontend | NEW file | Speed test execution logic |
| `client/src/api/speedtest.ts` | Frontend | NEW file | Speed test API |

**Modifications to existing files:**

| File | Change |
|------|--------|
| `server/app/main.py` | Include speedtest router |
| `server/app/models/enums.py` | Add `SpeedTestSize` enum (1MB, 5MB, 10MB, 50MB) |
| `client/src/App.tsx` | Add speed test button in header/settings |

**Implementation -- XHR-based measurement, not WebSocket:**

**Download test:**
```
1. Frontend starts timer
2. GET /api/speedtest/download?size=10485760
3. Server streams os.urandom() chunks via StreamingResponse
4. Frontend receives all data, stops timer
5. Speed = size / elapsed_time
```

**Upload test:**
```
1. Frontend generates random ArrayBuffer
2. Starts timer
3. POST /api/speedtest/upload with data as body
4. Server reads and discards, returns {bytes_received, server_time_ms}
5. Speed = size / elapsed_time (client-side timing)
```

**Architecture decision -- XHR over WebSocket:** XHR measures real HTTP transfer including TCP overhead, which matches what users experience during actual file transfers. WebSocket measures a different protocol path. The app already uses XHR for uploads, so this is consistent.

**Architecture decision -- streaming response over temp files:** Generating random data on-the-fly via `StreamingResponse` avoids temp files and works for any test size. Yield 64KB chunks of `os.urandom()`.

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| AuthMiddleware | Gate all requests when password set | ServerConfig, AuthService |
| AuthService | Hash verification, token signing | itsdangerous, bcrypt |
| ReadOnlyMiddleware | Block write operations | ServerConfig |
| DropBoxService | Drop box uploads, folder organization | FileService, ConnectionManager |
| ShareService | Token generation/validation | itsdangerous |
| DeviceService | Device tracking, User-Agent parsing | ConnectionManager |
| mDNSService | Network service registration | python-zeroconf |
| StatsCollector | Server metrics aggregation | Called by routers/services |
| TerminalUI | Rich Live dashboard | StatsCollector, ConnectionManager |
| SpeedTestRouter | Bandwidth measurement endpoints | StreamingResponse |

## Middleware Stack Order

Middleware executes in onion style in FastAPI (last registered = outermost). Register in this order:

```python
# In create_app():

# 1. ReadOnly (innermost -- only reached after auth passes)
if config.read_only:
    application.add_middleware(ReadOnlyMiddleware)

# 2. Auth (middle -- checks before read-only)
if config.password_hash is not None:
    application.add_middleware(AuthMiddleware, password_hash=config.password_hash)

# 3. CORS (outermost -- already exists, handles preflight OPTIONS)
application.add_middleware(CORSMiddleware, ...)
```

Request flow: CORS -> Auth -> ReadOnly -> Router.

## Data Flow Changes

### ServerConfig expansion

```python
class ServerConfig:
    shared_folder: Path
    port: int
    # v1.1 additions:
    password_hash: str | None    # bcrypt hash, None = no auth
    read_only: bool              # True = block all writes
    receive_mode: bool           # True = enable /drop endpoint
    receive_message: str         # Welcome message for drop box
```

### ServerInfo response expansion

```python
class ServerInfo(BaseModel):
    ip: str
    port: int
    url: str
    qr_svg: str
    all_ips: list[str]
    # v1.1 additions:
    read_only: bool              # Frontend hides write UI
    password_protected: bool     # Frontend shows lock icon
    receive_mode: bool           # Frontend shows drop box link
```

### WebSocket message types expansion

```python
class WSMessageType(str, Enum):
    # existing...
    TOAST = "toast"
    SNIPPET_UPDATED = "snippet_updated"
    # ...
    # v1.1 additions:
    DEVICE_LIST_UPDATED = "device_list_updated"
    DROPBOX_UPLOAD = "dropbox_upload"
```

## Patterns to Follow

### Pattern 1: Middleware for Cross-Cutting Concerns

**What:** Use Starlette middleware for concerns that apply to ALL endpoints.
**When:** Auth gating, read-only enforcement.

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, password_hash: str) -> None:
        super().__init__(app)
        self.password_hash = password_hash

    async def dispatch(self, request: Request, call_next):
        # Skip auth for login endpoint and share links
        if request.url.path.startswith("/api/auth") or request.url.path.startswith("/s/"):
            return await call_next(request)

        session_cookie = request.cookies.get("wfs_session")
        if session_cookie is None:
            return JSONResponse(status_code=401, content={"error": "Authentication required"})

        # Validate signed cookie via itsdangerous
        return await call_next(request)
```

### Pattern 2: Config-Driven Feature Flags

**What:** Feature availability determined by ServerConfig fields set at CLI parse time.
**When:** Features toggled via CLI flags (--password, --read-only, --receive).

```python
# In create_app():
config = get_server_config()
if config.password_hash is not None:
    app.add_middleware(AuthMiddleware, password_hash=config.password_hash)
if config.read_only:
    app.add_middleware(ReadOnlyMiddleware)
if config.receive_mode:
    app.include_router(dropbox_router)
```

### Pattern 3: Stateless Signed Tokens

**What:** itsdangerous `URLSafeTimedSerializer` for tokens with embedded payload and expiry.
**When:** Session cookies (auth) and share link tokens.

```python
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

serializer = URLSafeTimedSerializer(secret_key)
token = serializer.dumps({"path": "file.pdf"})

try:
    data = serializer.loads(token, max_age=3600)
except SignatureExpired:
    raise HTTPException(status_code=410, detail="Link has expired")
except BadSignature:
    raise HTTPException(status_code=403, detail="Invalid link")
```

### Pattern 4: Stats Collector Singleton

**What:** Thread-safe singleton aggregating server metrics, polled by terminal UI.
**When:** Terminal UI needs upload/download counts, bandwidth, activity log.

```python
import threading
from collections import deque

class StatsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.upload_count: int = 0
        self.download_count: int = 0
        self.total_bytes: int = 0
        self.recent_activity: deque[str] = deque(maxlen=20)

    def record_upload(self, filename: str, size: int) -> None:
        with self._lock:
            self.upload_count += 1
            self.total_bytes += size
            self.recent_activity.appendleft(f"Uploaded {filename}")
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Route Auth Checks

**What:** Adding `Depends(require_auth)` to each router endpoint.
**Why bad:** Easy to forget a route. A new endpoint added without the dependency is silently unprotected. Auth is a server-wide policy, not per-endpoint.
**Instead:** Middleware with explicit allowlist of unauthenticated paths.

### Anti-Pattern 2: Storing Password as Plaintext in Config

**What:** `ServerConfig.password = "mysecret"` instead of storing the hash.
**Why bad:** Password lives in memory for the server's lifetime. Debug endpoints or error handlers could leak it.
**Instead:** Hash at CLI parse time: `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`. Discard plaintext immediately.

### Anti-Pattern 3: Embedding Drop Box in App.tsx

**What:** Adding `mode === "dropbox"` conditional branch inside App.tsx.
**Why bad:** Drop box shares almost nothing with the file browser. Conditional rendering for an entirely different interface bloats App.tsx (already 500 lines) and couples unrelated concerns.
**Instead:** Separate Vite entry point (`drop-main.tsx`) and root component (`DropBox.tsx`). Shared utilities imported, but component tree is independent.

### Anti-Pattern 4: Database for Token Storage

**What:** Adding SQLite to store share link tokens for revocation.
**Why bad:** The project has no database. Adding one for a single feature is scope creep.
**Instead:** Stateless tokens via itsdangerous. Accept no pre-expiry revocation. For a LAN tool with short-lived tokens, this is fine. If revocation becomes critical, use an in-memory set of revoked IDs (cleared on restart).

### Anti-Pattern 5: Running Terminal UI on asyncio Event Loop

**What:** Making Rich Live an async task alongside uvicorn.
**Why bad:** Rich Live is designed for synchronous use with a background thread. Forcing it into async adds complexity with no benefit.
**Instead:** Run TUI refresh in a daemon thread. Use thread-safe StatsCollector for communication between async handlers and synchronous TUI.

## Suggested Build Order

Based on dependency analysis between features:

```
Phase 1: Access Control (establishes middleware + config patterns)
  1. Password Protection -- middleware, CLI, config expansion, itsdangerous
  2. Read-Only Mode -- second middleware, same patterns, quick to add

Phase 2: Sharing Features (uses itsdangerous from Phase 1)
  3. Expiring Share Links -- reuses itsdangerous serializer pattern
  4. Receive Mode / Drop Box -- separate entry point, uses upload infra

Phase 3: Server UX (independent of Phases 1-2)
  5. Device Discovery -- extends ConnectionManager, adds mDNS
  6. Terminal UI -- needs StatsCollector, benefits from device info
  7. Speed Test -- independent endpoint, simplest feature
```

**Rationale:**
- Password protection FIRST because it establishes the middleware pattern, itsdangerous usage, and config expansion approach that other features reuse.
- Read-only pairs with auth since both are middleware using the same base class.
- Share links reuse itsdangerous from auth, so serializer pattern is already established.
- Drop box is more complex (separate SPA, upload organization) but benefits from auth middleware being in place.
- Device discovery extends ConnectionManager; doing it before TUI means the dashboard can display device info.
- Terminal UI needs StatsCollector, which is touched by upload/download/device tracking -- so it comes after those exist.
- Speed test is the simplest, most independent feature. Can slot anywhere.

## Scalability Considerations

| Concern | At 3 devices | At 20 devices | At 100+ devices |
|---------|-------------|--------------|-----------------|
| WebSocket connections | Trivial | Fine, ~20 sockets | May need heartbeat tuning |
| Auth middleware | Negligible | Negligible | Cookie validation is O(1) |
| Device tracking | In-memory dict | In-memory dict | Paginate device list API |
| Share link tokens | Stateless | Stateless | No concern |
| mDNS broadcast | Single registration | Single registration | No concern |
| Terminal UI | 1s refresh | Same | Same |
| Speed test | One at a time | Concurrent possible | Rate-limit to prevent saturation |
| Drop box uploads | Direct to filesystem | Upload queue advisable | Upload size limits |

## Sources

- [FastAPI Response Cookies](https://fastapi.tiangolo.com/advanced/response-cookies/) -- cookie patterns (HIGH confidence)
- [itsdangerous documentation](https://itsdangerous.palletsprojects.com/en/stable/timed/) -- URLSafeTimedSerializer (HIGH confidence)
- [Rich Live Display](https://rich.readthedocs.io/en/latest/live.html) -- terminal dashboard (HIGH confidence)
- [Rich Progress Display](https://rich.readthedocs.io/en/latest/progress.html) -- progress bars (HIGH confidence)
- [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) -- mDNS discovery (HIGH confidence)
- [OpenSpeedTest](https://github.com/openspeedtest/Speed-Test) -- browser speed test reference (MEDIUM confidence)
- [FastAPI middleware discussion](https://github.com/fastapi/fastapi/issues/996) -- JWT cookie patterns (MEDIUM confidence)
- [Starlette SessionMiddleware](https://github.com/fastapi/fastapi/issues/754) -- session support (MEDIUM confidence)
