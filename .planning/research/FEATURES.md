# Feature Landscape: v1.3 Productionize Friend Tier

**Domain:** Cloud deployment hardening, relay infrastructure, and UX polish for a public-facing WebSocket relay + file sharing app
**Researched:** 2026-03-16
**Confidence:** HIGH (verified against Cloud Run docs, FastAPI ecosystem, existing codebase analysis)
**Scope:** v1.3 features ONLY. v1.0–v1.2 (file CRUD, preview, clipboard, real-time, remote mounts, tunnel protocol, agent CLI) are shipped and validated.

## Context

v1.2 shipped a full WebSocket relay tunnel: agent connects outbound, relay proxies browser HTTP through the tunnel, all SPA features work identically over remote mounts. The relay runs on `localhost:8001` with wildcard CORS, in-memory mount registry (lost on restart), and no rate limiting. v1.3 takes this to Google Cloud Run as a friend-tier public service — hardened, persistent, and polished.

Existing infrastructure v1.3 builds on:
- **Relay app** (`relay/app/`): `create_relay_app()`, `MountRegistry`, `agent_ws.py`, `mount_proxy.py`, `landing.py`, Jinja2 templates
- **Relay templates** (`relay/templates/`): `base.html`, `landing.html`, `not_found.html`, `offline.html`, `expired.html`
- **Auth middleware** (`server/app/middleware/auth_middleware.py`): bcrypt + itsdangerous cookie sessions, per-mount scoping
- **Agent CLI** (`agent/connection.py`): TTL countdown, reconnection loop, mount code assignment
- **React SPA** (`client/src/`): `ConnectionStatus.tsx` (green/red dot), `ReconnectingBanner`, `isRemoteMount()` util
- **Share links** (`server/app/services/share_service.py`): `ShareTTL` enum, itsdangerous tokens, background sweep pattern
- **pyproject.toml**: fastapi, uvicorn, jinja2, itsdangerous, bcrypt, websockets, httpx — no redis or postgres

---

## How These Features Work in Production Systems

### Persistent Mount Registries

Production tunnel services (ngrok, Cloudflare Tunnel, exposr) keep two tiers of state: (1) **metadata** (mount code, IP, TTL, status, password_hash) in a database and (2) **live connection handles** in memory. On restart, the DB survives; the agent reconnects and the relay re-associates the handle.

For single-instance deployments — Cloud Run `--min-instances=1` with `--max-instances=1` — the simpler pattern is an **SQLite file on a Cloud Storage volume mount**. Cloud Storage FUSE makes the file visible across Cloud Run lifecycle events. The key constraint: Cloud Storage FUSE has no POSIX file locking, so concurrent writes to SQLite can corrupt. The mitigation is `PRAGMA journal_mode=WAL` (write-ahead log) + ensuring only one writer at a time — correct for a single-instance relay. This is the right choice for a friends-tier service with low write frequency (mount registration is rare).

The critical insight: mount codes and metadata persist across deploys; **TunnelConnection objects never persist** — they hold live WebSocket state. On restart, agents reconnect and re-register their same code (if the relay accepts preferred codes, which the current `agent_ws.py` already supports via `?code=XXX`).

### Rate Limiting on Proxies

In production, rate limiting on a relay proxy has two distinct scopes:

1. **Mount registration rate limiting** (strict): Prevent IP from creating N mounts per hour. This is the abuse surface — an attacker can exhaust relay capacity by registering thousands of mounts. 5 mounts/hour per IP is standard for hobbyist services.

2. **Request proxying rate limiting** (lighter): Per-IP request/minute cap on `/m/{code}/*` to prevent one IP from flooding a single mount. 300 req/min per IP is a reasonable starting point — enough for normal browsing, too low for DDoS.

The FastAPI ecosystem standard is **slowapi** (wraps limits.py, the Python port of flask-limiter). For a single Cloud Run instance, in-memory storage is sufficient — no Redis needed. slowapi integrates via `app.state.limiter` and `@limiter.limit("5/hour")` decorators. The `get_remote_address` key function reads the real IP from `X-Forwarded-For` when behind a proxy (Cloud Run sets this header).

Anti-pattern: global rate limiter on the proxy route is too blunt — it penalizes all users for one IP's abuse. Per-IP is correct.

### File TTL / Auto-Deletion

In production file sharing services (WeTransfer, Firefox Send, tmpfile.link), per-file TTL means:
1. An `expires_at` timestamp stored alongside file metadata at upload time
2. A background sweep task that periodically deletes expired files
3. A "this file has expired" response for any access after expiry

For this project, the "file" is an upload into the receive-mode drop box folder. TTL deletion means the relay's default drop box mount exposes a receive-mode folder, and any file uploaded gets a deletion scheduled at `upload_time + TTL`. The sweep is an `asyncio` background task (same pattern as v1.1 share link sweeps in `share_service.py`).

The UI prompt ("restart to clear files") maps to the receive-mode pattern: when a file's TTL expires, it is deleted from the filesystem, and connected browsers receive a real-time notification (via existing WebSocket toast infrastructure).

### Public Drop Boxes

Production public drop boxes (JustBeamIt, OnionShare receive mode, Firefox Send) follow one pattern: **receive-only anonymous upload with no listing, optional password, auto-expiry**. The "always-on" variant runs as a background service that never stops.

For this project, the "default drop box" is the relay itself starting an agent subprocess on boot pointing to a temp directory in receive mode. This mount is registered under a well-known code (e.g., `dropbox`) so users can access it without an agent. The drop box mount never expires as a connection — individual files expire via per-file TTL. No password on the public drop box (open upload is the point).

Implementation detail: the relay process can `subprocess.Popen` or `asyncio.create_subprocess_exec` the agent on startup, pointing to a `tmpdir`. This avoids a separate container or process manager. The mount code is configured via env var (default: `dropbox`).

### Connection Status Indicators

In production real-time apps (Figma, Notion, Linear), connection status has four meaningful states:
1. **Connected** — WebSocket is open, server is reachable
2. **Reconnecting** — WebSocket closed, auto-retry in progress
3. **Host offline** — Relay reachable but agent has disconnected (503 from proxy)
4. **Expired** — Mount TTL elapsed (410 from proxy)

The existing `ConnectionStatus.tsx` and `ReconnectingBanner` cover states 1 and 2 (green/red dot + spinner). The gap for v1.3 is states 3 and 4 — the SPA needs to detect HTTP 503/410 responses from API calls and show appropriate overlays rather than broken partial UI. This maps to `api/client.ts` which already intercepts HTML error responses from the relay — it can be extended to detect status codes from relay error pages.

### Relay Landing Pages

Production relay landing pages (localtunnel, ngrok dashboard, teleport.sh) serve three purposes:
1. **Onboarding**: explain what the tool is for first-time visitors
2. **Code entry**: let recipients enter a mount code to reach the right mount
3. **Social discovery**: OG meta tags so link previews on Discord/Reddit/Twitter show useful info

The existing `landing.html` is minimal (form + brief text). v1.3 upgrades it with OG tags (`og:title`, `og:description`, `og:image`, `twitter:card`) in `base.html` so every page auto-previews, plus richer landing content (project description, GitHub link, demo mount link).

OG images must be at least 1200×630px and served from a stable URL. A simple static PNG bundled into the relay image and served at `/static/og-image.png` is sufficient.

### HTTPS Cookie Handling

Production apps running behind a TLS-terminating proxy (Cloud Run, nginx, AWS ALB) detect HTTPS via the `X-Forwarded-Proto: https` header injected by the proxy, not by inspecting the socket directly. The `Secure` cookie flag must be set when this header is present.

The existing auth middleware uses `itsdangerous` for session tokens. The `Secure` flag is set when creating the cookie response. FastAPI's `Response.set_cookie(secure=True)` plus an env var `RELAY_HTTPS=true` (or auto-detect from `X-Forwarded-Proto`) is the pattern.

### Cloud Run Docker Deployment

Cloud Run expects:
- Container listening on `$PORT` (default 8080, overridable)
- `GET /health` returning `{"status": "ok"}` with 200 for liveness probes
- Structured JSON logging to stdout (Cloud Run's log viewer parses JSON with `severity`, `message` keys)
- Single worker (Cloud Run scales by adding instances, not workers within an instance)
- `--min-instances=1` to keep WebSocket connections alive (WebSocket connections die when Cloud Run scales to zero)
- `--timeout=3600` (max session timeout, needed for long-lived agent WebSocket connections)
- `--session-affinity` (sticky routing so browser and agent hit the same instance)

For `uv`-based Python projects, the Dockerfile pattern is: copy `pyproject.toml` + `uv.lock`, `RUN uv sync --frozen --no-dev`, then copy source and run `uv run uvicorn`.

---

## Table Stakes

Features users expect. Missing = product feels broken or unusable as a public service.

| Feature | Why Expected | Complexity | Dependencies on Existing |
|---------|--------------|------------|--------------------------|
| **Cloud Run Docker deployment** | Without it, v1.3 has no delivery mechanism. Every other v1.3 feature runs in the container. | MEDIUM | `relay/app/main.py`, relay CLI, `pyproject.toml`. New: `Dockerfile`, `.dockerignore`, `GET /health` endpoint. |
| **HTTPS cookie Secure flag** | Cookies without `Secure` are sent over HTTP even on HTTPS connections. Auth cookies become visible to network sniffers. Cloud Run terminates TLS; relay must detect via `X-Forwarded-Proto`. | LOW | `server/app/middleware/auth_middleware.py` (cookie creation). New: `RELAY_HTTPS` env var or header detection. |
| **CORS lockdown (no wildcard)** | `allow_origins=["*"]` with `allow_credentials=True` is rejected by browsers. Current relay uses wildcard — safe for LAN but wrong for production. Must be the relay's own domain. | LOW | `relay/app/main.py` `CORSMiddleware` config. New: `RELAY_ALLOWED_ORIGINS` env var. |
| **Rate limiting — mount registration** | A public relay without per-IP mount caps is an open tunnel server. Anyone can register unlimited mounts. 5/hour per IP is the minimum for a public service. | LOW-MEDIUM | New: `slowapi` dep, limiter on `agent_ws.py` `/agent/ws` endpoint. |
| **SQLite persistent mount registry** | Cloud Run recycles instances on deploy or crash. All in-memory mount registrations are lost; agents can reconnect with their preferred code but any browser sessions break. SQLite on Cloud Storage mount is the correct approach for single-instance relay. | MEDIUM | `relay/app/services/mount_registry.py` (currently pure in-memory). New: SQLite schema, read/write operations, Cloud Storage volume mount config. |
| **Structured logging** | Cloud Run's log viewer only formats JSON logs with `severity`/`message` fields. Print statements produce unstructured text that's hard to query. Required for any production debugging. | LOW | Replace `print()` calls in relay and agent with `logging` module + JSON formatter. |
| **Health check endpoint** | Cloud Run liveness probes require `GET /health` returning 200. Without it, Cloud Run cannot detect unhealthy instances and restart them. | LOW | New: `GET /health` returning `{"status": "ok"}` in relay app. |

---

## Differentiators

Features that make v1.3 useful and polished beyond just "deployed relay."

| Feature | Value Proposition | Complexity | Dependencies on Existing |
|---------|-------------------|------------|--------------------------|
| **Relay landing page with OG meta tags** | When someone shares the relay URL on Discord or Reddit, the link preview currently shows nothing. OG tags turn a bare URL into a recognizable card with project name, description, and image. The landing page itself already exists (`landing.html`) — it just needs content and meta tags. | LOW | `relay/templates/landing.html` (exists, minimal). `relay/templates/base.html` (exists). New: OG meta tags block in `base.html`, richer landing content, static OG image asset. |
| **Connection status indicator — expanded states** | The existing `ConnectionStatus.tsx` shows green/red dot for WebSocket state. v1.3 adds "Host Offline" (agent disconnected, relay returns 503) and "Mount Expired" (410) states. Browser users currently see broken UI when the agent disconnects — this gives them a clear message and stops retry loops. | LOW | `ConnectionStatus.tsx` (exists, covers connected/reconnecting). `api/client.ts` (HTML error intercept exists). New: HTTP status detection for 503/410, full-page overlay component. |
| **Default always-on public drop box** | Users who don't have the agent CLI can still use the relay for anonymous file drops. The relay starts its own internal drop box mount on boot — no agent required. This is the "try it without installing anything" hook. | MEDIUM | `relay/app/main.py` (`create_relay_app()`). `agent/connection.py` (full agent logic). New: in-process or subprocess drop box startup, well-known mount code, env var config. |
| **Per-file upload TTL with auto-deletion** | Files uploaded to the drop box accumulate. Without TTL, the relay's temp folder fills up. TTL ensures uploaded files auto-delete after a configurable duration (default 24h) and the UI shows expiry info. Mirrors the v1.1 share link TTL pattern. | MEDIUM | `share_service.py` sweep pattern (reusable). File service upload handler. New: `expires_at` metadata per file, background sweep task, file-system deletion, UI notification via existing WebSocket toast. |
| **Rate limiting — proxy requests** | Per-IP request cap on `/m/{code}/*` prevents one IP from hammering a mount. Lighter limit than mount registration (300 req/min vs 5 mounts/hour). Protects the relay infrastructure and the agent behind it. | LOW | `relay/app/routers/mount_proxy.py`. New: `@limiter.limit("300/minute")` on `proxy_request`. |
| **Mandatory mount TTL on relay** | Public relay should enforce a maximum mount duration (default 24h, configurable). Agents can still set shorter TTLs via `--ttl`. The relay overrides indefinite mounts to the max. Prevents forgotten mounts from occupying codes indefinitely. | LOW | `relay/app/routers/agent_ws.py` (mount registration). `relay/app/services/mount_registry.py` (`MountRecord`). New: `MAX_MOUNT_TTL_SECONDS` env var, TTL enforcement on registration, background sweep for relay-side expiry. |
| **Max concurrent mounts per IP cap** | Beyond rate limiting, a hard cap (e.g., 3 active mounts per IP) prevents sustained abuse where an attacker registers mounts slowly enough to slip past the per-hour rate limit. | LOW | `relay/app/services/mount_registry.py`. New: IP tracking in `MountRecord`, cap check on registration. |

---

## Anti-Features

Features to explicitly NOT build in v1.3.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Redis for rate limiting / registry** | Adds a paid external dependency (Cloud Memorystore ~$40/month, or Upstash free tier with quota). Unnecessary for a single-instance relay. slowapi works with in-memory storage; SQLite handles registry persistence. | In-memory slowapi counters for rate limiting. SQLite on Cloud Storage for registry persistence. Revisit if scaling past one instance. |
| **Multi-instance Cloud Run** | Multiple instances break the relay: each instance has its own in-memory TunnelConnection objects, and agents connect to one instance while browsers hit another. The SQLite-on-FUSE approach also doesn't support multi-writer safely. | `--max-instances=1` on Cloud Run. Session affinity via `--session-affinity`. Single instance is correct for a friends-tier service. |
| **E2E encryption** | Massive scope: requires browser-side WebAssembly crypto, key exchange protocol, and breaks relay's ability to inspect/proxy HTTP (which it needs for header rewriting). Deferred to v2 in PROJECT.md. | TLS transport (HTTPS on Cloud Run handles this). Document the relay trust model. |
| **Custom domains for mounts** | Requires CNAME → relay DNS setup, per-subdomain TLS provisioning (Let's Encrypt ACME), and wildcard cert management. Transforms the relay into a PaaS. Out of scope per PROJECT.md. | Mount codes work well. Short codes are the UX differentiator. |
| **Per-user accounts / auth on relay** | Adding a user layer to the relay requires a users table, registration flow, email verification. This is a separate milestone (v1.4+) per PROJECT.md. | Public relay with rate limiting is sufficient for friends tier. Password on individual mounts (v1.1 feature) handles access control at the mount level. |
| **Bandwidth metering / caps** | Tracking bytes per mount requires intercepting streaming responses and accumulating counters — adds latency to every chunk. The simpler abuse prevention (mount caps + request rate limits) is sufficient for a friends service. | Mount count caps + request rate limits. Revisit if bandwidth costs become a problem. |
| **Per-file deduplication or compression** | Deduplication requires content-addressed storage; compression requires buffering streaming responses. Both violate the pure-proxy model. | Let clients handle compression if needed. No server-side file caching per PROJECT.md. |
| **SameSite=Strict cookies on relay** | `SameSite=Strict` breaks the relay's core flow: when a user follows a link to `/m/{code}/`, the browser is making a cross-site navigation and Strict cookies aren't sent on the first request. The user always hits the login page even with a valid session. | `SameSite=Lax` (current setting). Lax is correct: cookies are sent on top-level navigations (following links) but not on cross-site sub-requests. |

---

## Feature Dependencies

```
Cloud Run Deployment (Dockerfile, /health, structured logging)
    |
    +-- enables --> All other v1.3 features (they all run inside the container)
    |
    +-- requires --> HTTPS Cookie Secure Flag (Cloud Run is HTTPS-only)
    |
    +-- requires --> CORS Lockdown (wildcard CORS + allow_credentials is browser-rejected over HTTPS)

SQLite Persistent Mount Registry
    |
    +-- requires --> Cloud Run Deployment (Cloud Storage volume mount only available in Cloud Run)
    |
    +-- extends --> MountRegistry (relay/app/services/mount_registry.py — replace in-memory dict)
    |
    +-- enables --> Mandatory Mount TTL (TTL metadata persists across restarts)

Rate Limiting (slowapi)
    |
    +-- requires --> Cloud Run Deployment (public surface is what needs protecting)
    |
    +-- applies-to --> agent_ws.py /agent/ws (mount registration — strict limit)
    |
    +-- applies-to --> mount_proxy.py /m/{code}/{path} (proxy requests — lighter limit)
    |
    +-- requires --> Real IP from X-Forwarded-For (Cloud Run proxy header, configure slowapi)

Relay Landing Page with OG Tags
    |
    +-- extends --> relay/templates/landing.html (exists, minimal)
    +-- extends --> relay/templates/base.html (add OG meta block)
    +-- requires --> Static file serving (FastAPI StaticFiles for OG image asset)
    +-- independent of --> SQLite, Rate Limiting, Cloud Run (works locally too)

Connection Status Indicator — Expanded States
    |
    +-- extends --> ConnectionStatus.tsx (green/red dot, ReconnectingBanner — already shipped)
    +-- extends --> api/client.ts (HTML error intercept — already shipped)
    +-- new --> HTTP 503 / 410 status detection and full-page overlay
    +-- independent of --> SQLite, Rate Limiting

Default Always-On Drop Box
    |
    +-- requires --> Cloud Run Deployment (must auto-start in the container)
    +-- requires --> Per-file Upload TTL (drop box without TTL accumulates files forever)
    +-- reuses --> Receive mode (--receive flag on agent — already in v1.1)
    +-- reuses --> MountRegistry (registers its own mount under a well-known code)

Per-file Upload TTL
    |
    +-- requires --> Default Drop Box (files need a home with TTL semantics)
    +-- reuses --> ShareTTL enum pattern (v1.1 share_service.py)
    +-- reuses --> WebSocket toast infrastructure (notify on deletion)
    +-- new --> expires_at metadata per uploaded file, background asyncio sweep, filesystem deletion
```

### Critical Dependency Notes

- **Cloud Run first.** The Dockerfile and deployment setup is the foundation. Every other feature either runs inside it or depends on the HTTPS context it provides.
- **CORS + cookies must be fixed before any auth testing in production.** The current `allow_origins=["*"]` combined with cookies breaks in Chrome when `allow_credentials=True`.
- **SQLite on Cloud Storage FUSE has no file locking.** Must use `PRAGMA journal_mode=WAL`. Must enforce `--max-instances=1` on Cloud Run. Never run two relay instances pointing at the same SQLite file.
- **Rate limiting key function must read `X-Forwarded-For` not socket IP.** Cloud Run terminates TLS/TCP at the load balancer; the socket IP is always the Google infrastructure IP. Configure slowapi's key function to trust the `X-Forwarded-For` header.
- **Drop box mount must start after relay app is fully initialized.** If the relay app starts the drop box agent in `lifespan` startup, the mount registry must already be initialized. Use FastAPI `lifespan` context manager (not deprecated `on_event`).
- **Per-file TTL sweep must run only in the relay process, not in the agent.** Files live on the agent's filesystem; the agent is responsible for deletion. The relay only tracks metadata about which files have TTLs.

---

## Expected Behavior Per Feature

### 1. Cloud Run Deployment

**How it works in production:**
- `Dockerfile`: `FROM python:3.11-slim`, install `uv`, copy `pyproject.toml` + `uv.lock`, `RUN uv sync --frozen --no-dev`, copy source, `CMD ["uv", "run", "uvicorn", "relay.app.main:app", "--host", "0.0.0.0", "--port", "8080"]`
- `GET /health` returns `{"status": "ok", "mounts": N}` with HTTP 200. Cloud Run hits this every 10s by default.
- Cloud Run config: `--min-instances=1 --max-instances=1 --timeout=3600 --session-affinity --memory=512Mi`
- Structured logging: Python `logging.getLogger()` + `json.dumps({"severity": "INFO", "message": "..."})` to stdout. Cloud Run auto-parses.
- `.dockerignore`: exclude `node_modules/`, `client/node_modules/`, `.planning/`, `feature-ideas/`, `tests/`, `*.md`

**Complexity: MEDIUM.** New Dockerfile + health endpoint + logging refactor + Cloud Run config. ~4-6 hours including first deploy and debugging.

### 2. SQLite Persistent Mount Registry

**How it works in production:**
- SQLite file at `/data/relay.db` (mounted Cloud Storage bucket)
- Schema: `mounts(code TEXT PRIMARY KEY, agent_ip TEXT, status TEXT, created_at INTEGER, expires_at INTEGER NULL, max_connections INTEGER)`
- `PRAGMA journal_mode=WAL` set on connection open
- On relay start: read all rows, mark any ONLINE rows as OFFLINE (agent hasn't reconnected yet)
- On mount registration: `INSERT OR REPLACE INTO mounts ...`
- On mount deregistration: `UPDATE mounts SET status='OFFLINE'` (keep history)
- On TTL expiry: `UPDATE mounts SET status='EXPIRED'`
- `MountRegistry._connections` dict stays in-memory (holds live `TunnelConnection` objects, not persisted)

**Complexity: MEDIUM.** SQLite schema + CRUD + Cloud Storage volume config + migration from in-memory. ~4-6 hours.

### 3. Rate Limiting

**How it works in production:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)  # reads X-Forwarded-For

# On /agent/ws:
@limiter.limit("5/hour")  # mount registration
async def agent_websocket(...): ...

# On /m/{code}/{path}:
@limiter.limit("300/minute")  # proxy requests
async def proxy_request(...): ...
```
Returns HTTP 429 with `Retry-After` header on violation. The `get_remote_address` function in slowapi reads `X-Forwarded-For` by default, which is correct for Cloud Run.

**Complexity: LOW.** Add `slowapi` dep + decorators + exception handler + configure for Cloud Run IP headers. ~2 hours.

### 4. CORS Lockdown

**How it works in production:**
```python
# relay/app/main.py
ALLOWED_ORIGINS = os.environ.get("RELAY_ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
`RELAY_ALLOWED_ORIGINS=https://your-relay.run.app` in Cloud Run env vars. Falls back to wildcard for local dev.

**Complexity: LOW.** 10 lines of config change + env var. ~1 hour.

### 5. Relay Landing Page with OG Tags

**How it works in production:**
- `base.html` gets an OG meta block in `<head>`:
  ```html
  <meta property="og:title" content="Network File Server" />
  <meta property="og:description" content="Share files with anyone — scan a QR or enter a mount code." />
  <meta property="og:image" content="{{ og_image_url }}" />
  <meta property="og:url" content="{{ canonical_url }}" />
  <meta name="twitter:card" content="summary_large_image" />
  ```
- `landing.html` gets richer content: project description, "How it works" (3 steps), GitHub link, demo mount link
- Static OG image (1200×630 PNG) bundled in the image, served via `StaticFiles` at `/static/og-image.png`
- `landing.py` injects `og_image_url` and `canonical_url` from env vars

**Complexity: LOW.** Template updates + static file serving + OG image. ~2-3 hours.

### 6. Connection Status Indicator — Expanded States

**How it works in production:**
- `ConnectionStatus.tsx` adds two new states beyond existing green/red:
  - **Host Offline** (agent disconnected): shown when relay returns 503 on any API call
  - **Mount Expired** (TTL elapsed): shown when relay returns 410 on any API call
- `api/client.ts` already intercepts HTML responses from the relay — extend to detect HTTP 503/410 status codes (even non-HTML responses)
- Full-page overlay component (like a modal) replaces partial broken UI: "Host Offline — the owner's device has disconnected. Reconnecting automatically..." with a spinner, or "This mount has expired" with no retry
- Existing `ReconnectingBanner` covers WebSocket reconnection (state 2) — no change needed

**Complexity: LOW.** React component extension + status code detection. ~2-3 hours.

### 7. Default Always-On Drop Box

**How it works in production:**
- Relay process spawns the agent on startup pointing to a tmpdir: `asyncio.create_subprocess_exec("uv", "run", "network-file-server", "mount", str(tmpdir), "--server", "http://localhost:8080", "--receive", "--code", drop_box_code)`
- `drop_box_code` is configurable via `DROPBOX_MOUNT_CODE` env var (default: `dropbox`)
- Drop box mount never expires as a connection — the relay manages its lifecycle
- Drop box is in receive mode (`--receive`): upload-only, no file listing for anonymous visitors
- No password on drop box (open upload is the point)
- Landing page includes a "Try it: Upload a file to our demo drop box" link pointing to `/m/dropbox/`

**Complexity: MEDIUM.** Subprocess lifecycle management + startup integration + landing page link. ~4 hours.

### 8. Per-file Upload TTL

**How it works in production:**
- At upload time: create `{filename}.meta.json` alongside each uploaded file with `{"expires_at": unix_timestamp, "original_name": "..."}`
- Default TTL: 24h (configurable via `UPLOAD_TTL_HOURS` env var in the drop box agent)
- Background asyncio task in the file server (not relay): sweep every 10 minutes, delete files where `expires_at < now()`
- On deletion: broadcast WebSocket notification via existing toast infrastructure ("File 'photo.jpg' was automatically deleted after 24 hours")
- UI: file listing shows an expiry badge on files near expiration (within 1 hour)

**Complexity: MEDIUM.** Per-file metadata, asyncio sweep task, filesystem deletion, UI badge. ~4-6 hours.

---

## MVP Definition

### v1.3 Core (Deploy-Gate — Must Ship First)

These features either enable the deployment or fix security issues that make production unsafe:

- [ ] **Cloud Run Dockerfile** — container + health check + structured logging + deploy config
- [ ] **HTTPS cookie Secure flag** — `X-Forwarded-Proto` detection, `Secure` on session cookies
- [ ] **CORS lockdown** — `RELAY_ALLOWED_ORIGINS` env var, no wildcard in production

### v1.3 Hardening (Ship With Core — Safety Layer)

- [ ] **Rate limiting — mount registration** — slowapi, 5/hour per IP
- [ ] **Rate limiting — proxy requests** — slowapi, 300/min per IP
- [ ] **Mandatory mount TTL** — max 24h, env-configurable

### v1.3 Persistence (Ship After Core — Reliability)

- [ ] **SQLite persistent mount registry** — Cloud Storage volume mount, WAL mode, status tracking

### v1.3 Polish (Ship Last — UX)

- [ ] **Relay landing page with OG tags** — meta tags in base.html, richer landing content, static OG image
- [ ] **Connection status indicator — expanded states** — 503/410 detection, full-page overlay
- [ ] **Default always-on drop box** — subprocess agent, `DROPBOX_MOUNT_CODE` env var
- [ ] **Per-file upload TTL** — metadata file, background sweep, toast notification

---

## Complexity Summary

| Feature | Complexity | Hours | Phase Candidate |
|---------|------------|-------|-----------------|
| Cloud Run Docker deployment | MEDIUM | 4-6h | Phase 1 (deploy gate) |
| HTTPS cookie Secure flag | LOW | 1-2h | Phase 1 (deploy gate) |
| CORS lockdown | LOW | 1h | Phase 1 (deploy gate) |
| Health check endpoint | LOW | 0.5h | Phase 1 (deploy gate) |
| Structured logging | LOW | 1-2h | Phase 1 (deploy gate) |
| Rate limiting (both endpoints) | LOW-MEDIUM | 2-3h | Phase 2 (hardening) |
| Mandatory mount TTL on relay | LOW | 1h | Phase 2 (hardening) |
| Max mounts per IP cap | LOW | 1h | Phase 2 (hardening) |
| SQLite persistent registry | MEDIUM | 4-6h | Phase 3 (persistence) |
| Relay landing page + OG tags | LOW | 2-3h | Phase 4 (polish) |
| Connection status expanded states | LOW | 2-3h | Phase 4 (polish) |
| Default always-on drop box | MEDIUM | 4h | Phase 4 (polish) |
| Per-file upload TTL | MEDIUM | 4-6h | Phase 4 (polish) |

**Total estimated: 28-44 hours across 4 phases.**

---

## Sources

- [Cloud Run container health check configuration](https://docs.cloud.google.com/run/docs/configuring/healthchecks) — HIGH confidence (official docs)
- [Cloud Run Cloud Storage volume mounts](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts) — HIGH confidence (official docs)
- [slowapi GitHub — rate limiter for FastAPI/Starlette](https://github.com/laurentS/slowapi) — HIGH confidence (official repo)
- [FastAPI CORS configuration — production best practices](https://fastapi.tiangolo.com/tutorial/cors/) — HIGH confidence (official docs)
- [Open Graph meta tag best practices — DEV Community testing](https://dev.to/shadowfaxrodeo/i-tested-every-link-preview-meta-tag-on-every-social-media-and-messaging-app-so-you-dont-have-to-it-was-super-boring-39c0) — MEDIUM confidence (community)
- [SQLite on Cloud Run with Cloud Storage FUSE](https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun/) — MEDIUM confidence (community guide)
- [WebSocket readyState and connection status in React](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/readyState) — HIGH confidence (MDN)
- Codebase analysis: `relay/app/`, `relay/templates/`, `client/src/components/ConnectionStatus.tsx`, `client/src/api/client.ts`, `agent/connection.py`, `server/app/services/share_service.py`, `pyproject.toml` — HIGH confidence

---

*Feature research for: Network File Server v1.3 Productionize Friend Tier*
*Researched: 2026-03-16*
