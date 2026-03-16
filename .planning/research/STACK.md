# Technology Stack

**Project:** Network File Server — v1.3 Productionize Friend Tier
**Researched:** 2026-03-16
**Scope:** NEW additions only — existing stack (FastAPI, uvicorn, pydantic, bcrypt, itsdangerous, jinja2, aiofiles, websockets, httpx, httpx-ws) is validated and unchanged.

---

## Guiding Principle: Minimal New Dependencies

Every new dependency must pull its weight. v1.3 is a productionization milestone — correctness, security, and operability matter more than features. When stdlib or existing libraries cover a need, use them. When a new library is justified, pin to a specific minimum version that has been verified.

---

## New Stack Additions

### Rate Limiting

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `slowapi` | `>=0.1.9` | Per-IP rate limiting on relay endpoints — mount connect rate, landing page, upload endpoints | Direct port of flask-limiter for Starlette/FastAPI. Zero external services needed — uses in-memory storage by default (fine for single-instance Cloud Run with `--min-instances=1`). Decorator-based `@limiter.limit("5/minute")` integrates at the route level without rewriting middleware. No Redis dependency. v0.1.9 is the latest stable release (released February 2024, still maintained). |

**Verification:** slowapi 0.1.9 confirmed on PyPI. `limits` package (its backend) handles in-memory storage with no Redis. The project currently has CORS wildcard and zero rate limiting — slowapi is the smallest correct fix.

**What NOT to use:** `fastapi-limiter` requires Redis. Writing custom rate-limit middleware in asyncio is error-prone and untestable. slowapi is the standard recommendation for FastAPI without Redis.

---

### Async SQLite (Persistent Mount Registry)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `aiosqlite` | `>=0.22.0` | Async SQLite access for mount registry persistence | The relay currently uses an in-memory `dict` for mount registry. v1.3 adds SQLite persistence so registered mounts survive relay restarts. `aiosqlite` wraps Python stdlib `sqlite3` with an asyncio interface — no ORM, no migrations framework, no extra surface area. One file. One table. Queries are simple enough that raw SQL with `aiosqlite` is cleaner than SQLAlchemy for this scope. |

**Verification:** aiosqlite 0.22.1 released December 23, 2025. Actively maintained by the Omnilib project. Works with Python 3.11+.

**Cloud Run constraint — important:** Cloud Run instances have ephemeral filesystems. SQLite on a bare local path (`./mounts.db`) survives between requests on the same instance but is wiped on redeploy or scale-to-zero. The relay MUST be deployed with `--min-instances=1` (keeps one warm instance alive), and the DB file written to `/tmp/mounts.db` within the container. This is acceptable because:
1. Mount codes are short-lived — agents reconnect and get new codes on relay restart.
2. The *persistent* value is surviving within-session relay restarts (e.g., container crash), not cross-deploy persistence.
3. Full cross-deploy persistence would require Cloud Storage FUSE (high-latency, no file locking) or Cloud SQL ($50+/month) — both disproportionate for this use case.

**What NOT to use:** SQLAlchemy — adds ORM complexity for a single-table registry. Cloud SQL — $50/month for a two-column table. Cloud Storage FUSE for SQLite — no file locking, high write latency, officially unsupported for databases by GCP.

---

### Structured Logging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `structlog` | `>=25.0.0` | JSON-formatted structured logs to stdout for Cloud Run / Cloud Logging ingestion | Cloud Run captures stdout and pipes to Google Cloud Logging. Cloud Logging parses JSON logs natively — severity, trace, message, and arbitrary fields become queryable. `structlog` outputs JSON in production and human-readable logs in dev via a single env-var toggle. Integrates with Python stdlib `logging` so FastAPI/uvicorn access logs are captured in the same format. No external agent or sidecar needed. v25.5.0 is the latest (released October 2025). |

**Verification:** structlog 25.5.0 confirmed on PyPI (GitHub releases). Well-maintained (Hynek Schlawack). FastAPI integration documented with request context binding.

**What NOT to use:** `python-json-logger` — less ergonomic, fewer features, less actively maintained. `google-cloud-logging` SDK — adds 15MB of GCP client deps; structured stdout is sufficient and simpler for Cloud Run. Raw `logging.basicConfig` with a JSON formatter — works but structlog's processor pipeline is cleaner for adding per-request context.

---

### Configuration / Environment Variables

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pydantic-settings` | `>=2.13.0` | Typed settings class that reads from environment variables and `.env` files | Cloud Run injects config as environment variables (`RELAY_ALLOWED_ORIGINS`, `RELAY_MAX_MOUNTS_PER_IP`, `RELAY_DB_PATH`, etc.). `pydantic-settings` validates and types them at startup — fail-fast if a required var is missing. Dev uses `.env` file. Production uses Cloud Run env vars. This replaces the current hardcoded defaults in `relay/cli.py`. Already indirectly used (pydantic is a project dep) — `pydantic-settings` is a lightweight separate package that plugs in with zero friction. |

**Verification:** pydantic-settings 2.13.1 released February 19, 2026. Part of the Pydantic organization. FastAPI officially recommends it for settings management (https://fastapi.tiangolo.com/advanced/settings/).

**What NOT to use:** `python-dotenv` alone — no type validation. `os.environ.get()` scattered inline — untestable, no schema. `dynaconf` — heavy, not idiomatic for FastAPI.

---

## Per-File Upload TTL: No New Dependency

The per-file upload TTL feature (auto-delete uploaded files after N minutes) does NOT require APScheduler or any external task library. The existing stack already has everything needed:

**Pattern:** `asyncio.create_task()` with `asyncio.sleep()` spawned at upload time.

```python
async def _schedule_file_deletion(path: Path, ttl_seconds: int) -> None:
    await asyncio.sleep(ttl_seconds)
    path.unlink(missing_ok=True)

# In upload handler:
asyncio.create_task(_schedule_file_deletion(uploaded_path, ttl_seconds))
```

**Why no APScheduler:** APScheduler 3.x (stable, v3.11.2) requires a separate scheduler object, job stores, and startup/shutdown hooks. For a fire-and-forget deletion that runs once after N seconds, `asyncio.create_task` is the stdlib primitive designed exactly for this. APScheduler 4.x is still in alpha (4.0.0a6, not production-safe per maintainer). No new dependency is justified.

**Caveat:** If the relay process dies before TTL fires, the file is not deleted. This is acceptable — the feature is best-effort auto-cleanup, not a security guarantee. The "restart prompt" in PROJECT.md covers this case at the UX level.

---

## Connection Status UI: No New Dependency

The React frontend already has WebSocket infrastructure. Connection status (online/offline/expired) is implemented as:
- A new WebSocket message type in the existing tunnel protocol
- A React context/state hook consuming the existing WebSocket connection
- No new frontend library needed — Tailwind CSS (already in use) handles the indicator styling

---

## CORS Lockdown: No New Dependency

The relay currently uses `CORSMiddleware` with `allow_origins=["*"]`. Lockdown is a configuration change, not a library change:

```python
# Before (v1.2 — wildcard)
allow_origins=["*"]

# After (v1.3 — env-var driven list)
allow_origins=settings.allowed_origins  # e.g. ["https://yourrelay.run.app"]
```

`pydantic-settings` handles parsing a comma-separated `RELAY_ALLOWED_ORIGINS` env var into a `list[str]`. No additional CORS library needed.

---

## Cloud Run Deployment: No New Python Dependency

The Dockerfile and Cloud Run configuration are infrastructure concerns, not Python library concerns:

**Dockerfile pattern:**
```dockerfile
FROM python:3.11-slim-bullseye
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev
COPY . .
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "uvicorn", "relay.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Health check:** A `GET /healthz` endpoint returning `{"status": "ok"}` — pure FastAPI route, no library.

**Structured logging to stdout:** Handled by `structlog` (see above) + `PYTHONUNBUFFERED=1` env var so logs flush immediately to Cloud Logging.

**Secure cookie flags (HTTPS):** `itsdangerous` already handles cookie signing. HTTPS `Secure` and `SameSite=Strict` flags are set conditionally based on a `RELAY_ENV=production` env var in the existing cookie-setting code. No new library.

---

## Default Always-On Drop Box Mount: No New Dependency

The default public drop box is a relay feature — an always-registered mount that the relay server itself "hosts" (no external agent). This requires:
- A mount registered at relay startup with a fixed well-known code
- The mount proxied to a local in-process FastAPI "sub-app" (using `httpx.ASGITransport` — already in the stack from v1.2 agent work)
- The sub-app serves a simple receive-only filesystem rooted at `/tmp/dropbox/`

`httpx.ASGITransport` is already used by the agent to proxy tunnel requests locally. The same pattern works here — the relay registers a "self" mount that routes to an internal ASGI app. Zero new dependencies.

---

## Updated pyproject.toml Dependencies

```toml
[project]
dependencies = [
    # Existing (unchanged from v1.2)
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
    "httpx>=0.28.0",
    "websockets>=13.0",
    "httpx-ws>=0.8.2",
    # NEW for v1.3
    "slowapi>=0.1.9",          # Per-IP rate limiting — no Redis needed
    "aiosqlite>=0.22.0",       # Async SQLite for persistent mount registry
    "structlog>=25.0.0",       # JSON structured logging for Cloud Run/Cloud Logging
    "pydantic-settings>=2.13.0",  # Typed env-var config for Cloud Run deployment
]
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Rate limiting | `slowapi` | `fastapi-limiter` | Requires Redis — no Redis in this deployment |
| Rate limiting | `slowapi` | Custom asyncio middleware | Untestable, reinvents a solved problem |
| Async DB access | `aiosqlite` | SQLAlchemy + asyncpg | Over-engineered for a single-table registry |
| Async DB access | `aiosqlite` | Cloud SQL | $50/month minimum for two-column table |
| Persistent DB on Cloud Run | SQLite in `/tmp/` + min-instances=1 | Cloud Storage FUSE | No file locking, high latency, GCP docs say "don't use for databases" |
| Structured logging | `structlog` | `python-json-logger` | Less maintained, less ergonomic processor pipeline |
| Structured logging | `structlog` | `google-cloud-logging` SDK | 15MB of GCP client library for a stdout formatter |
| Config management | `pydantic-settings` | `python-dotenv` + `os.environ` | No type validation, no fail-fast on missing vars |
| File TTL | asyncio.create_task + sleep | `APScheduler` 3.x | Heavyweight for fire-and-forget one-shot tasks |
| File TTL | asyncio.create_task + sleep | `APScheduler` 4.x | Still alpha/pre-release, not production-safe |
| CORS lockdown | Config change to existing `CORSMiddleware` | `fastapi-cors` library | Existing middleware already supports `allow_origins` list |
| Drop box mount | Internal ASGI sub-app via `httpx.ASGITransport` | Separate process/agent | Unnecessary process management complexity |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Redis | No horizontal scaling needed; min-instances=1 keeps one warm instance | in-memory storage (slowapi default) |
| Cloud SQL / PostgreSQL | $50+/month minimum; mount registry is a 2-column table | SQLite in `/tmp/` |
| `celery` / task queues | File TTL is a one-shot asyncio sleep, not a distributed job | `asyncio.create_task` |
| `APScheduler` | Still alpha in v4; v3.x adds lifecycle complexity for one-shot tasks | `asyncio.create_task` |
| `google-cloud-logging` SDK | Adds 15MB of client libs; Cloud Run reads stdout natively | `structlog` to stdout |
| `alembic` | No migration history needed; schema is a single CREATE TABLE IF NOT EXISTS | Raw `aiosqlite` DDL at startup |
| ORM (SQLAlchemy) | Single-table registry doesn't benefit from ORM abstraction | Raw SQL with `aiosqlite` |
| `fastapi-limiter` | Requires Redis | `slowapi` with in-memory backend |
| Multiple Cloud Run instances | SQLite requires single-writer; rate limiting state is per-instance | `--min-instances=1 --max-instances=1` |

---

## Integration Points

### slowapi Integration

`slowapi` attaches to the FastAPI app as a state attribute and middleware. Key integration:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Routes with limits use `@limiter.limit("5/minute")` with `request: Request` as first param. The relay's agent registration endpoint and mount proxy landing should be rate-limited to prevent abuse.

**Behind Cloud Run's load balancer:** `get_remote_address` reads `X-Forwarded-For` — correct for Cloud Run (GCP sets this header). No additional proxy-header middleware needed.

### aiosqlite Integration

`MountRegistry` gains an `AsyncSQLiteRegistry` implementation. Schema:

```sql
CREATE TABLE IF NOT EXISTS mounts (
    code TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
```

The in-memory `TunnelConnection` reference cannot be stored in SQLite (it's a live WebSocket). The registry stores metadata in SQLite and live connections in a separate in-memory `dict`. On relay startup, SQLite is read to restore `OFFLINE` status for any codes registered before the restart — agents reconnecting with a known code can reclaim their slot.

### structlog Integration

Configure at relay app startup (before any log calls):

```python
import structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),  # production
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
```

In development (detected via `RELAY_ENV != "production"`), swap `JSONRenderer` for `ConsoleRenderer` for human-readable output.

### pydantic-settings Integration

```python
from pydantic_settings import BaseSettings

class RelaySettings(BaseSettings):
    relay_env: str = "development"
    relay_db_path: str = "/tmp/mounts.db"
    relay_allowed_origins: list[str] = ["*"]
    relay_max_mounts_per_ip: int = 5
    relay_default_mount_ttl_s: int = 86400  # 24h

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
```

Constructed once at module level with `@lru_cache`. Passed into `create_relay_app()` for middleware and router configuration.

---

## Sources

- [slowapi PyPI](https://pypi.org/project/slowapi/) — v0.1.9, in-memory backend confirmed, no Redis required
- [slowapi GitHub](https://github.com/laurentS/slowapi) — FastAPI/Starlette integration, `get_remote_address` for X-Forwarded-For
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) — v0.22.1 released December 23, 2025
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/latest/) — async context manager API, Python >=3.8 compatible
- [structlog PyPI / docs](https://www.structlog.org/) — v25.5.0 released October 2025, JSONRenderer for production
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) — v2.13.1 released February 19, 2026
- [FastAPI settings docs](https://fastapi.tiangolo.com/advanced/settings/) — official recommendation for pydantic-settings
- [Cloud Run min-instances docs](https://docs.cloud.google.com/run/docs/configuring/min-instances) — keeps warm instance, avoids cold-start / SQLite loss
- [Cloud Run Cloud Storage FUSE limitations](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts) — no file locking, high latency — confirms SQLite on FUSE is wrong approach
- [Cloud Run FastAPI quickstart](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service) — updated 2026-03-12, Dockerfile patterns
- [APScheduler versions](https://pypi.org/project/APScheduler/) — v4.0a6 confirmed pre-release/alpha, v3.11.2 stable but heavyweight for one-shot tasks

---
*Stack research for: v1.3 Productionize Friend Tier*
*Researched: 2026-03-16*
