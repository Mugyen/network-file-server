# Architecture Patterns

**Domain:** v1.3 Productionize Friend Tier — Cloud Run hardening of existing relay
**Researched:** 2026-03-16
**Confidence:** HIGH

---

## System Overview (v1.2 Baseline — What Already Exists)

```
                           INTERNET
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │   ┌──────────────────────────────────────────────────────────┐   │
  │   │           RELAY SERVER  (relay/app/main.py)              │   │
  │   │                                                          │   │
  │   │  create_relay_app()                                      │   │
  │   │  ├── CORSMiddleware(allow_origins=["*"])   ← REPLACE     │   │
  │   │  ├── landing router   GET /                              │   │
  │   │  ├── agent_ws router  WS /agent/ws                       │   │
  │   │  └── mount_proxy router  HTTP+WS /m/{code}/{path}        │   │
  │   │                                                          │   │
  │   │  MountRegistry (in-memory dict)            ← REPLACE     │   │
  │   │  {code -> MountRecord(conn, MountStatus)}                │   │
  │   └──────────────────────────────────────────────────────────┘   │
  │                           ▲                                       │
  │                           │ WebSocket /agent/ws                  │
  │                           │                                       │
  │   Browser                 │                Agent (behind NAT)    │
  │   ┌──────────┐            │              ┌──────────────────────┐ │
  │   │ React    │ HTTP/WS    │              │ agent/connection.py  │ │
  │   │ SPA      │────────────┘              │ run_agent_loop()     │ │
  │   │ served   │                           │                      │ │
  │   │ at       │                           │ TunnelConnection     │ │
  │   │ /m/{code}│                           │ → ASGITransport      │ │
  │   └──────────┘                           │ → create_app()       │ │
  │                                          └──────────────────────┘ │
  └──────────────────────────────────────────────────────────────────┘
```

The relay is a single FastAPI process. The in-memory `MountRegistry` maps 8-char codes to `TunnelConnection` objects. The tunnel protocol uses binary frames with 21-byte headers and UUID stream multiplexing. The agent connects outbound via WebSocket, proxies requests to a local `create_app()` instance via `httpx.ASGITransport`.

---

## v1.3 Features: Integration Analysis

Each v1.3 feature is analyzed as: what it touches, how it fits, and what it adds.

### Feature 1: Cloud Run Deployment (Docker + PORT + health check)

**What changes:** Build system only. Zero application code changes required.

**Integration point:** `relay/cli.py` already reads `--port` via argparse. Cloud Run injects `$PORT` as an environment variable. The relay CLI needs to check `$PORT` env before falling back to the hardcoded default of 8001.

```
Current:  port = args.port if args.port is not None else 8001
Required: port = args.port if args.port is not None else int(os.environ.get("PORT", "8001"))
```

**New artifacts:**
- `relay/Dockerfile` — multi-stage build (uv builder stage → slim runtime stage)
- `relay/.dockerignore` — exclude client source, test files, planning docs
- `relay/app/routers/health.py` — `GET /health` returning `{"status": "ok"}` for Cloud Run startup probe

**No changes to:** tunnel protocol, mount proxy, agent WS router, React SPA, landing page.

**Pattern:** Cloud Run injects `$PORT` (usually 8080). Container must listen on `0.0.0.0:$PORT`. Health check probe hits `/health` — Cloud Run marks instance healthy when it responds 200.

```
Dockerfile pattern (multi-stage with uv):
  Stage 1 (builder):  FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
                      COPY pyproject.toml uv.lock ./
                      RUN uv sync --frozen --no-dev --no-install-project
                      COPY relay/ relay/
                      COPY tunnel/ tunnel/
                      RUN uv sync --frozen --no-dev

  Stage 2 (runtime):  FROM python:3.11-slim-bookworm
                      COPY --from=builder /app/.venv /app/.venv
                      ENV PATH="/app/.venv/bin:$PATH"
                      ENV PYTHONUNBUFFERED=1
                      CMD ["sh", "-c", "uvicorn relay.app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
```

**HTTPS cookies:** `relay/app/routers/agent_ws.py` does not set cookies. The per-mount auth cookies are set by the agent's local `create_app()` instance and proxied transparently. Those cookies need `Secure; SameSite=None` when the relay runs on HTTPS. This is set in `server/app/middleware/auth_middleware.py`'s `Set-Cookie` response header — a one-line change to add `secure=True` conditionally when `RELAY_HTTPS=true` env var is set.

---

### Feature 2: SQLite Persistent Mount Registry

**What changes:** `relay/app/services/mount_registry.py` — the registry gains a SQLite persistence layer. The in-memory dict is NOT removed; it remains the runtime source of truth. SQLite stores mount metadata (code, name, ttl, created_at) that survives restarts.

**Why keep in-memory:** `TunnelConnection` objects are not serializable (they contain live WebSocket state). SQLite stores mount *metadata*; the active connections still live in memory. On restart, SQLite shows which codes were previously registered — useful for the agent's preferred_code reconnect feature.

**Integration point:** `relay/app/services/mount_registry.py` — add a `MountPersistence` class alongside the existing `MountRegistry`. The `MountRegistry` calls `MountPersistence` on register/deregister.

**New module:** `relay/app/services/mount_persistence.py`

```
MountPersistence
├── __init__(db_path: str)  — opens aiosqlite connection, creates table
├── async save_mount(code, name, ttl_seconds, created_at)
├── async remove_mount(code)
└── async load_all_mounts() -> list[MountRow]   — used at startup
```

**Database schema:**
```sql
CREATE TABLE IF NOT EXISTS mounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL,   -- unix timestamp
    ttl_seconds INTEGER,           -- NULL = no TTL
    password_hash BLOB             -- NULL = no password
);
```

**Lifespan integration:** `create_relay_app()` currently has no lifespan handler. Add one using FastAPI's `@asynccontextmanager` lifespan pattern:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    persistence = MountPersistence(db_path=os.environ.get("DB_PATH", "/data/relay.db"))
    await persistence.initialize()
    set_persistence(persistence)
    yield
    await persistence.close()
```

**Cloud Run storage:** Cloud Run filesystem is ephemeral. For persistence across deploys, mount a Cloud Storage bucket via GCS FUSE as a volume at `/data/`. The SQLite file lives at `/data/relay.db`. GCS FUSE has no file locking — this is acceptable because the relay is single-instance (Cloud Run max-instances=1 for this use case) and SQLite WAL mode handles concurrent reads from the same process.

**MEDIUM confidence warning:** GCS FUSE SQLite has documented no-file-locking limitation. For this app (low write frequency — one write per mount/unmount, not per request), this is safe. If max-instances > 1 is ever needed, migrate to Cloud Firestore or Cloud SQL.

---

### Feature 3: Rate Limiting and Abuse Prevention

**What changes:** `relay/app/main.py` — add SlowAPI middleware. New module: `relay/app/middleware/rate_limit.py`.

**What to rate limit:**
1. `/agent/ws` — agent connection registration: 10 mounts per IP per hour (prevents code exhaustion)
2. `POST /m/{code}/api/files/upload` — upload bandwidth: 20 uploads per IP per minute
3. `GET /` landing page — 60 requests per IP per minute (bot protection)
4. All routes as global fallback — 120 requests per IP per minute

**Library:** SlowAPI (wraps limits-based rate limiting, works with FastAPI/Starlette). Confidence: HIGH — well-established, works without Redis for single-instance deployments.

**Integration:**
```python
# relay/app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
```

**Mandatory TTL for agent connections:** The `/agent/ws` endpoint currently accepts agents with no TTL. Add enforcement: if `ttl_seconds` is not provided in the connection query params, assign a default maximum TTL (e.g., 24 hours). This prevents indefinite connections accumulating.

**Per-IP mount cap:** At `/agent/ws` registration time, the `MountRegistry` checks how many active mounts exist from the connecting IP. If it exceeds 5 (configurable via env var `MAX_MOUNTS_PER_IP`), reject with 429.

**Important:** SlowAPI's in-memory storage does not survive restart and is not shared across instances. For single-instance Cloud Run (max-instances=1), this is acceptable. If scaling horizontally, switch to Redis storage.

---

### Feature 4: CORS Lockdown

**What changes:** `relay/app/main.py` — replace wildcard `allow_origins=["*"]` with explicit origin list.

**Current state:** `CORSMiddleware(allow_origins=["*"])` — this is what v1.2 ships with.

**Why it matters for Cloud Run:** CORS is a browser defense. The relay serves browser clients. With `allow_origins=["*"]` and no `allow_credentials=True`, cookies are NOT sent cross-origin. But API endpoints that don't use credentials are callable from any origin — including malicious sites that might abuse the relay.

**New pattern:**
```python
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")
if not allowed_origins or allowed_origins == [""]:
    # Development fallback — permissive
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,    # required for cookie-based auth
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "X-Device-Name"],
)
```

**Env var `ALLOWED_ORIGINS`:** Set in Cloud Run to the relay's own domain (e.g., `https://relay.example.com`). In local dev, omit for permissive fallback.

**Note:** `allow_credentials=True` + explicit origins (not `*`) is the CORS spec-compliant combination for cookie-based auth. This is a required change for HTTPS production cookies to work.

---

### Feature 5: Per-File Upload TTL with Auto-Deletion

**What changes:** Server-side (`server/app/`) — new TTL tracking layer on uploads. This lives in the local server that the agent runs, NOT in the relay.

**Integration point:** `server/app/services/file_service.py` upload path + a new background task scheduler.

**Data model:** Upload TTL metadata stored as a sidecar JSON file (`.nfs-meta/<filename>.json`) or as an in-memory dict in a new `UploadTTLService`. The in-memory approach is simpler and matches the "ephemeral is a feature" philosophy.

**New module:** `server/app/services/upload_ttl_service.py`
```
UploadTTLService
├── schedule_deletion(file_path: Path, ttl_seconds: int)
│     — creates asyncio.Task that sleeps then unlinks the file
├── cancel_deletion(file_path: Path)
│     — cancels pending task if file is explicitly deleted first
└── list_pending() -> list[PendingDeletion]
      — returns all scheduled deletions with remaining seconds
```

**Trigger:** The upload endpoint (`POST /api/files/upload`) gains an optional `ttl_seconds` query param. If provided, after successful upload, `UploadTTLService.schedule_deletion()` is called.

**UI integration:** When a file has a pending TTL deletion, the file listing API (`GET /api/files`) should include a `ttl_expires_at` field in `FileEntry`. The React SPA can show a countdown badge on the file card.

**Restart prompt:** When the local server restarts, in-memory TTL state is lost. On agent startup, if the shared folder has been used before, the agent prints: "Warning: upload TTLs are lost on restart. Files uploaded with TTL may outlive their expiry." This is acceptable behavior — the user controls the agent process.

**Default public drop box mount:** This feature (always-on mount on Cloud Run) uses `--receive` mode. The default drop box is started by the relay's own startup logic, not by an external agent. This requires the relay to optionally self-host a local drop box:

```python
# relay/app/main.py — lifespan addition
if os.environ.get("ENABLE_DROP_BOX") == "true":
    drop_box_path = Path(os.environ.get("DROP_BOX_PATH", "/tmp/dropbox"))
    drop_box_path.mkdir(exist_ok=True)
    asyncio.create_task(start_embedded_agent(drop_box_path))
```

The embedded agent runs `run_agent_loop()` in-process, targeting `ws://localhost:{port}/agent/ws`. This means the relay connects to itself as both relay and agent — no separate process needed on Cloud Run.

---

### Feature 6: Connection Status WebSocket Events

**What changes:** React SPA — `client/src/hooks/useWebSocket.ts` + `client/src/components/ConnectionStatus.tsx`. The relay — `relay/app/routers/mount_proxy.py` (optional: relay can send a control message when mount status changes).

**Current state:** The SPA's `useWebSocket` hook already has reconnect logic and `ConnectionStatus` component showing "Reconnecting..." banner. When in remote mode (`isRemoteMount() === true`), the WS is connected to the local agent's `/ws` endpoint via the tunnel.

**What v1.3 adds:** A `status` event pushed by the relay or agent over the existing WebSocket tunnel when mount state changes (e.g., agent is about to expire, relay restarts, TTL countdown).

**Two approaches:**

*Option A — Relay-side status endpoint (recommended):* Add `GET /m/{code}/status` on the relay returning `{"status": "online"|"offline"|"expired", "ttl_remaining": N}`. The SPA polls this every 30 seconds in remote mode. No new WebSocket channel needed.

*Option B — WebSocket status frame:* The relay sends a JSON control message over the existing WS tunnel when mount status changes. This is lower latency but more complex.

Option A is recommended because polling is simpler, the relay already knows mount status from `MountRegistry`, and it doesn't require any tunnel protocol changes.

**UI indicator:** The `ConnectionStatus` component is extended to show three states:
- Online (green dot) — mount is ONLINE
- Offline (yellow dot) — mount is OFFLINE (agent disconnected, may reconnect)
- Expired (red dot, no reconnect) — mount TTL elapsed, manual action required

The indicator is only shown in remote mount mode (`isRemoteMount() === true`).

---

### Feature 7: Relay Landing Page Branding and OG Tags

**What changes:** `relay/templates/landing.html` — existing file gets extended with branding, OG meta tags, and improved mount code entry form.

**Current state:** The landing page exists (`relay/app/routers/landing.py`) and renders `landing.html`. The page likely has a basic form. The router already handles `GET /?code=ABC` redirect to `/m/{code}/`.

**What v1.3 adds:**
- Open Graph meta tags (`og:title`, `og:description`, `og:image`) for social sharing previews
- App name / tagline branding in the page header
- Improved copy and visual hierarchy

**Integration point:** Pure template change. No Python code changes needed.

---

## Component Map: New vs Modified vs Unchanged

| Component | File(s) | v1.3 Status | What Changes |
|-----------|---------|-------------|--------------|
| **Health endpoint** | `relay/app/routers/health.py` | NEW | `GET /health` → `{"status": "ok"}` |
| **Dockerfile** | `relay/Dockerfile` | NEW | Multi-stage uv build for Cloud Run |
| **Dockerignore** | `relay/.dockerignore` | NEW | Exclude non-runtime files |
| **MountPersistence** | `relay/app/services/mount_persistence.py` | NEW | aiosqlite-backed mount metadata store |
| **UploadTTLService** | `server/app/services/upload_ttl_service.py` | NEW | asyncio-task-based TTL deletion scheduler |
| **Rate limit config** | `relay/app/middleware/rate_limit.py` | NEW | SlowAPI limiter configuration |
| **create_relay_app()** | `relay/app/main.py` | MODIFIED | Add lifespan, SlowAPI, CORS lockdown, health router, drop box task |
| **relay/cli.py** | `relay/cli.py` | MODIFIED | Read `$PORT` env var; add `--db-path` flag |
| **MountRegistry** | `relay/app/services/mount_registry.py` | MODIFIED | Call `MountPersistence` on register/deregister; add per-IP mount count |
| **agent_ws router** | `relay/app/routers/agent_ws.py` | MODIFIED | Enforce mandatory TTL default; enforce per-IP mount cap |
| **mount_proxy router** | `relay/app/routers/mount_proxy.py` | MODIFIED | Add `GET /m/{code}/status` endpoint for SPA polling |
| **auth_middleware** | `server/app/middleware/auth_middleware.py` | MODIFIED | Add `Secure; SameSite=None` to cookies when `RELAY_HTTPS` env set |
| **files upload router** | `server/app/routers/files.py` | MODIFIED | Accept optional `ttl_seconds` query param, call `UploadTTLService` |
| **file listing schema** | `server/app/models/schemas.py` | MODIFIED | Add `ttl_expires_at: int | None` to `FileEntry` |
| **landing template** | `relay/templates/landing.html` | MODIFIED | Add OG tags, branding, improved form |
| **ConnectionStatus** | `client/src/components/ConnectionStatus.tsx` | MODIFIED | Show online/offline/expired states in remote mode |
| **useWebSocket** | `client/src/hooks/useWebSocket.ts` | MODIFIED | Poll `/m/{code}/status` in remote mode |
| **FileList/FileCard** | `client/src/components/FileList.tsx` | MODIFIED | Show TTL countdown badge when `ttl_expires_at` present |
| **TunnelConnection** | `tunnel/connection.py` | UNCHANGED | Binary protocol unchanged |
| **Tunnel frames** | `tunnel/frames.py` | UNCHANGED | Frame format unchanged |
| **agent/connection.py** | `agent/connection.py` | UNCHANGED (mostly) | run_agent_loop reused for embedded drop box |
| **mount_proxy** (proxy logic) | `relay/app/routers/mount_proxy.py` | UNCHANGED | HTTP + WS proxying unchanged |
| **create_app()** | `server/app/main.py` | UNCHANGED | LAN server factory unchanged |
| **file_service.py** | `server/app/services/file_service.py` | UNCHANGED | File operations unchanged |

---

## Data Flow Changes

### Mount Registration (v1.3 addition)

```
Agent WS /agent/ws?code=preferred
    │
    ▼
agent_ws router
    │  1. Check per-IP mount count (MountRegistry.count_by_ip)
    │     → 429 if exceeded MAX_MOUNTS_PER_IP
    │  2. Assign code, wrap in TunnelConnection
    │  3. registry.register(code, conn)
    │     → MountPersistence.save_mount(code, ...) [async, non-blocking]
    │  4. Enforce TTL default if not provided
    │
    ▼
Agent receives {"type": "mount_registered", "code": "..."}
```

### Relay Restart Recovery

```
Relay restarts (Cloud Run redeploy)
    │
    ▼
lifespan startup
    │  1. MountPersistence.initialize() — connects to SQLite
    │  2. MountPersistence.load_all_mounts() — reads previously registered codes
    │  3. For each loaded code: log "Previously registered mount {code} — awaiting reconnect"
    │     (No connection exists yet; agents reconnect via run_agent_loop's preferred_code)
    │
    ▼
Agent reconnects with preferred_code=last_assigned_code
    │
    ▼
agent_ws router assigns the same code (preferred_code not occupied → reuse)
    │
    ▼
Mount URL is stable across relay restarts ✓
```

### Connection Status Poll (SPA side)

```
SPA loads at /m/{code}/ (isRemoteMount() === true)
    │
    ▼
useWebSocket detects remote mode
    │  Every 30s: fetch /m/{code}/status
    │
    ▼
mount_proxy GET /m/{code}/status handler
    │  — try registry.get_connection(code)
    │  — ONLINE: {"status": "online", "ttl_remaining": N | null}
    │  — MountOfflineError: {"status": "offline"}
    │  — MountExpiredError: {"status": "expired"}
    │  — MountNotFoundError: {"status": "not_found"}
    │
    ▼
ConnectionStatus component updates indicator
```

### Upload with TTL

```
Browser: POST /api/files/upload?path=...&ttl_seconds=3600
    │
    ▼
(Through tunnel → agent → local create_app())
    │
    ▼
files router upload handler
    │  1. file_service.upload_file(...)  [existing]
    │  2. if ttl_seconds: upload_ttl_service.schedule_deletion(file_path, ttl_seconds)
    │
    ▼
UploadTTLService creates asyncio.Task:
    │  asyncio.sleep(ttl_seconds) → file_path.unlink(missing_ok=True)
    │
    ▼
FileEntry in GET /api/files includes ttl_expires_at for scheduled files
```

---

## Architectural Patterns for v1.3

### Pattern 1: Lifespan-Managed Services (FastAPI lifespan)

**What:** All services that need startup/shutdown (SQLite connection, drop box task, rate limiter state) are initialized in the FastAPI `@asynccontextmanager` lifespan handler, not at module import time.

**Why:** Cloud Run may spin up multiple instances during a deploy. Module-level side effects are harder to control than lifespan-scoped initialization. Lifespan also guarantees clean shutdown before Cloud Run terminates the instance.

**Pattern:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup
    persistence = MountPersistence(db_path=_resolve_db_path())
    await persistence.initialize()
    set_persistence(persistence)
    registry = MountRegistry()
    set_registry(registry)
    # optional embedded drop box
    drop_box_task: asyncio.Task | None = None
    if os.environ.get("ENABLE_DROP_BOX") == "true":
        drop_box_task = asyncio.create_task(_start_drop_box())
    yield
    # shutdown
    if drop_box_task is not None:
        drop_box_task.cancel()
    await persistence.close()
```

### Pattern 2: Environment-Driven Configuration

**What:** All production-specific behavior is controlled by environment variables, not code branches. Development defaults are permissive (CORS=*, no auth, in-memory only). Production env sets restrictive values.

**Env vars:**
| Variable | Development Default | Production Value |
|----------|--------------------|--------------------|
| `PORT` | 8001 | 8080 (Cloud Run injects) |
| `ALLOWED_ORIGINS` | `""` (wildcard fallback) | `https://relay.example.com` |
| `DB_PATH` | `/tmp/relay-dev.db` | `/data/relay.db` (GCS mount) |
| `MAX_MOUNTS_PER_IP` | `100` | `5` |
| `RELAY_HTTPS` | `false` | `true` |
| `ENABLE_DROP_BOX` | `false` | `true` |
| `DROP_BOX_PATH` | `/tmp/dropbox` | `/data/dropbox` (GCS mount) |

### Pattern 3: Status Polling over New WebSocket Channel

**What:** The connection status indicator uses REST polling (`GET /m/{code}/status`) instead of a dedicated status WebSocket. The existing WS tunnel already carries real-time events from the local server; a second WS channel for relay-level status adds complexity without proportional benefit.

**Why polling is correct here:** Status changes are rare events (mount offline, TTL expired). 30-second polling introduces at most 30-second lag in status display. The cost of a missed event (user sees "online" for 30 extra seconds after agent disconnects) is negligible. The cost of maintaining a second bidirectional WS channel (relay-to-browser) is non-trivial — it would require the relay to maintain a browser WS connection registry alongside the agent WS registry.

---

## Anti-Patterns to Avoid in v1.3

### Anti-Pattern 1: SQLite Without WAL on GCS FUSE

**What goes wrong:** Default SQLite journal mode (`DELETE`) holds an exclusive lock during writes. GCS FUSE has no file locking support. Concurrent reads during a write may corrupt the database.

**Prevention:** Enable WAL mode in `MountPersistence.initialize()`:
```python
await conn.execute("PRAGMA journal_mode=WAL")
await conn.execute("PRAGMA synchronous=NORMAL")
```
WAL mode allows concurrent readers while one writer is active. The relay has only one writer (itself), so this is safe.

### Anti-Pattern 2: Running Rate Limiter Across Multiple Instances

**What goes wrong:** SlowAPI's default in-memory storage is per-process. If Cloud Run scales to 2+ instances, each instance has its own rate limit counter. An abuser can hit 5x the configured rate by hitting 5 instances.

**Prevention:** Set Cloud Run `--max-instances=1` for the relay. The relay is a stateful service (WebSocket connections); multiple instances require sticky sessions anyway. For this use case, single-instance is correct. Document this constraint explicitly.

### Anti-Pattern 3: Cookies Without Secure Flag on HTTPS

**What goes wrong:** Auth cookies set without `Secure=True` over HTTPS are sent in plaintext fallback requests. Also, `SameSite=Lax` blocks cross-site requests needed for the relay pattern. Browsers may reject the cookie.

**Prevention:** `AuthMiddleware.set_cookie()` must check `RELAY_HTTPS` env var and add `secure=True, samesite="none"` when running on HTTPS.

### Anti-Pattern 4: Embedding the Drop Box Agent at Module Import

**What goes wrong:** If `run_agent_loop()` is called at module import time (e.g., in a module-level `asyncio.run()`), it blocks the event loop before the FastAPI app is ready to accept connections. The agent connects to `/agent/ws` which doesn't exist yet.

**Prevention:** Start the embedded agent task inside the lifespan handler, after the relay app is fully initialized. Use `asyncio.create_task()` so it runs concurrently with request handling.

### Anti-Pattern 5: Storing TTL State in the Relay

**What goes wrong:** Per-file upload TTL is a feature of the local server (the folder being shared). Putting TTL tracking in the relay (or in SQLite on the relay) creates a split state problem: the relay knows about file TTLs but the file lives on the agent's local disk.

**Prevention:** Upload TTL state lives exclusively in `UploadTTLService` inside the agent's local `create_app()` instance. The relay knows nothing about file TTLs. The relay's SQLite stores mount-level metadata only (code, name, created_at, mount TTL).

---

## Build Order (Dependency-Driven)

Each step is independently testable. Dependencies are shown explicitly.

| Order | Feature | Depends On | Test Without |
|-------|---------|------------|--------------|
| 1 | Health endpoint (`GET /health`) | Nothing | Everything — trivial 200 response |
| 2 | `relay/cli.py` `$PORT` env var | Nothing | Cloud Run — test with `PORT=9000 uv run network-relay` |
| 3 | CORS lockdown (`ALLOWED_ORIGINS` env) | Nothing | Browsers — test with curl to verify headers |
| 4 | `relay/Dockerfile` + `.dockerignore` | #1, #2 | Cloud Run — test with `docker build && docker run` |
| 5 | SQLite `MountPersistence` | Nothing | Everything — unit-testable with tmp file |
| 6 | Relay lifespan + `MountPersistence` integration | #5 | Nothing — integration test restart recovery |
| 7 | Rate limiting middleware | Nothing | Load testing — `slowapi` unit-testable |
| 8 | Agent WS: per-IP cap + mandatory TTL default | #7 | Drop box — test with multiple agent connects |
| 9 | `GET /m/{code}/status` endpoint | Existing `MountRegistry` | SPA — testable with curl |
| 10 | `ConnectionStatus` SPA indicator | #9 | Nothing — full E2E works |
| 11 | `UploadTTLService` | Existing file_service | Nothing — unit-testable with tmp dir |
| 12 | Upload endpoint `ttl_seconds` param | #11 | Drop box — testable with curl |
| 13 | `FileEntry.ttl_expires_at` in API | #11 | SPA badge — testable with curl |
| 14 | SPA file card TTL badge | #13 | Nothing — final E2E |
| 15 | `RELAY_HTTPS` env var + Secure cookies | #4 | Production — test with ngrok or Cloud Run staging |
| 16 | Default drop box embedded agent | #6, #8 | Cloud Run — test with `ENABLE_DROP_BOX=true` locally |
| 17 | Landing page OG tags + branding | Nothing | Everything — pure HTML/template change |

**Rationale for ordering:**
- Steps 1-4 first because they unblock Cloud Run deployment testing early. You want a working Docker image before writing all other features.
- SQLite persistence (#5-6) before rate limiting (#7-8) because the lifespan handler must be in place before adding more lifespan-scoped services.
- Connection status (#9-10) before upload TTL (#11-14) because status is relay-side (simpler, no protocol changes) while TTL touches server + SPA.
- Secure cookies (#15) and drop box (#16) last — they require a working HTTPS deployment to fully test.
- Landing page (#17) is pure HTML; it has no dependencies and can be done at any point.

---

## New Dependencies

| Package | Current | Why Needed | Confidence |
|---------|---------|------------|-----------|
| `aiosqlite` | Not in pyproject.toml | Async SQLite for MountPersistence | HIGH — standard library, no alternatives needed |
| `slowapi` | Not in pyproject.toml | Rate limiting middleware | HIGH — standard choice for FastAPI/Starlette, no Redis needed for single instance |

All other features use existing dependencies (FastAPI lifespan, asyncio tasks, existing env var patterns).

---

## Scaling Considerations

| Concern | v1.3 (single instance) | If scaled later |
|---------|------------------------|-----------------|
| Rate limiting | In-memory per-process (SlowAPI default) | Migrate to Redis-backed SlowAPI |
| SQLite | GCS FUSE single writer (WAL mode) | Migrate to Cloud Firestore or Cloud SQL |
| Mount registry | In-memory (runtime) + SQLite (metadata) | Add Cloud Pub/Sub for cross-instance mount events |
| Drop box | Embedded in-process agent | Break out as separate Cloud Run service |

**For v1.3:** Single instance is the correct deployment model. Document `--max-instances=1` in the Cloud Run deployment instructions. The relay is stateful (WebSocket connections) — horizontal scaling requires sticky sessions, which adds infrastructure complexity out of scope for v1.3.

---

## Sources

- [Cloud Run Volume Mounts (GCS FUSE)](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts) — official GCS FUSE volume mount docs
- [SQLite on Cloud Run with GCS FUSE](https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun/) — SQLite + GCS FUSE pattern with WAL mode
- [GCS FUSE limitations (no file locking)](https://discuss.google.dev/t/connecting-cloud-run-to-a-persistent-storage-solution/124337) — confirmed locking limitation
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — lifespan context manager pattern
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) — async SQLite library
- [SlowAPI GitHub](https://github.com/laurentS/slowapi) — FastAPI/Starlette rate limiting
- [SlowAPI in-memory multi-instance caveat](https://github.com/laurentS/slowapi/issues/226) — confirmed per-process limitation
- [Cloud Run PORT env var](https://cloud.google.com/run/docs/configuring/services/environment-variables) — Cloud Run injects PORT, must not hardcode
- [Cloud Run health checks](https://docs.cloud.google.com/run/docs/configuring/healthchecks) — startup probe configuration
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) — multi-stage Dockerfile patterns
- [FastAPI CORS production 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026) — CORS lockdown with `allow_credentials=True`
- [Cloud Run min-instances](https://docs.cloud.google.com/run/docs/configuring/min-instances) — keep-warm instance for WebSocket services

---
*Architecture research for: v1.3 Productionize Friend Tier — Cloud Run hardening of relay*
*Researched: 2026-03-16*
