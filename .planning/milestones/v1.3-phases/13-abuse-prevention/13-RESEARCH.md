# Phase 13: Abuse Prevention - Research

**Researched:** 2026-03-17
**Domain:** Rate limiting, TTL enforcement, and configuration management for a FastAPI relay server
**Confidence:** HIGH

## Summary

This phase adds abuse prevention to the relay server: rate limiting mount registration and proxy requests, enforcing mount TTL with server-side capping, capping concurrent mounts per IP, and centralizing all relay configuration into a YAML-based config module. The primary library is SlowAPI (v0.1.9), a FastAPI/Starlette rate limiter that wraps the `limits` library for storage and strategy. SlowAPI supports in-memory storage with moving-window strategy (confirmed: `limits` MemoryStorage implements `MovingWindowSupport` via a timestamp list). PyYAML is already installed in the project (v6.0.3) so no new YAML dependency is needed.

The existing relay codebase has clear integration points: `create_relay_app()` factory for middleware/lifespan hooks, router-based organization for per-route rate limits, singleton registry pattern for config, and Jinja2 error templates for styled 429 pages. The agent already supports `--ttl` with client-side countdown; this phase adds server-side enforcement so the relay controls TTL regardless of agent behavior.

**Primary recommendation:** Use SlowAPI with `strategy="moving-window"` and in-memory storage, a custom key function extracting client IP from X-Forwarded-For (matching existing pattern at mount_proxy.py:85-88), FastAPI lifespan for the TTL background sweep, and a dedicated `relay/app/config.py` module loading `relay/config.yaml` with env var overrides.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Browser requests hitting 429 get a styled Jinja2 error page (consistent with existing not_found/offline/expired templates)
- Error page shows the exact retry countdown (driven by Retry-After header value), e.g. "Try again in 45 seconds"
- Agent mount registration failures return JSON `{"error": "...", "retry_after": N}` -- agent CLI prints the message and exits (no auto-retry)
- Rate-limited requests logged at WARNING level with client IP for abuse monitoring in Cloud Logging
- Sliding window algorithm for both mount registration and proxy request rate limits
- Use SlowAPI library (built on `limits`) -- supports sliding window, in-memory storage, Retry-After headers, per-route config
- In-memory storage -- counters reset on relay restart, which is acceptable for single-instance Cloud Run
- Client IP extraction via X-Forwarded-For header (consistent with existing mount_proxy.py:85-88 pattern); SlowAPI custom key function
- Agent specifies TTL as query parameter on WebSocket URL: `/agent/ws?code=abc&ttl=3600` (consistent with existing `?code=` pattern)
- Relay caps requested TTL to configured maximum (default 24h) -- agent cannot exceed the cap
- On TTL expiry: immediate disconnect -- relay marks mount EXPIRED and closes agent WebSocket; browser requests get existing "expired" error page (HTTP 410)
- Relay sends `{"type": "ttl_warning", "expires_in": 300}` control message 5 minutes before expiry so agent can notify user
- Periodic asyncio background sweep (every 30-60s) checks all mounts and disconnects expired ones
- Create a dedicated config module (`relay/app/config.py`) that loads `relay/config.yaml`
- Single `relay/config.yaml` with development defaults checked into the repo
- Env vars override YAML values (12-factor app style for Cloud Run deployments)
- Absorb all existing relay config into the module: RELAY_ENV, RELAY_ALLOWED_ORIGINS, plus all new rate limit settings
- All rate limit thresholds configurable: mount registration rate (default 5/hr), proxy request rate (default 300/min), max TTL (default 24h), max concurrent mounts per IP (default 5)
- Config module should handle loading, serialization, and validation -- not just a dict wrapper
- The config.yaml approach is preferred over scattered env vars for all relay configuration going forward
- Existing RELAY_ENV and RELAY_ALLOWED_ORIGINS should migrate into config.yaml (env vars still work as overrides)

### Claude's Discretion
- Exact SlowAPI middleware integration approach (app-level vs per-router)
- Config YAML schema structure and field naming
- Background sweep interval (30s vs 60s)
- How env var names map to YAML keys (e.g., RELAY_RATE_MOUNT_REG or similar)
- Whether to validate config.yaml on startup or lazily

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ABUSE-01 | Mount registration is rate-limited to 5 per hour per IP | SlowAPI `@limiter.limit("5/hour")` on agent_ws endpoint with custom key_func extracting X-Forwarded-For |
| ABUSE-02 | Proxy requests to `/m/{code}/*` are rate-limited to 300 per minute per IP | SlowAPI `@limiter.limit("300/minute")` on proxy_request endpoint with same key_func |
| ABUSE-03 | Relay enforces a maximum mount TTL (default 24h, configurable via env var) -- agents cannot create indefinite mounts | TTL query param on WebSocket URL, relay caps to config max, asyncio background sweep expires mounts |
| ABUSE-04 | Maximum concurrent mounts per agent IP is capped (default 5, configurable via env var) | MountRegistry gains per-IP tracking via `agent_ip` field on MountRecord; checked before registration |
| ABUSE-05 | Rate limit violations return HTTP 429 with `Retry-After` header | SlowAPI `headers_enabled=True` adds Retry-After; custom exception handler returns styled HTML or JSON |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slowapi | 0.1.9 | Rate limiting for FastAPI | Most widely used FastAPI rate limiter; wraps `limits` library; supports per-route decorators, custom key functions, multiple strategies |
| limits | 5.8.0 | Rate limit storage and strategies (transitive dep of slowapi) | Provides MemoryStorage, MovingWindowRateLimiter, and rate limit string parsing |
| pyyaml | 6.0.3 | YAML config file parsing | Already installed in project; standard Python YAML library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| fastapi | >=0.115.0 | Already in project | Lifespan events for background sweep startup/shutdown |
| jinja2 | >=3.1.0 | Already in project | Styled 429 error template |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SlowAPI | fastapi-limiter | fastapi-limiter requires Redis; SlowAPI supports in-memory storage which matches our single-instance Cloud Run model |
| SlowAPI | Hand-rolled middleware | SlowAPI handles Retry-After headers, rate limit string parsing, per-route config, and exception handling out of the box |
| PyYAML | pydantic-settings | pydantic-settings is heavier and adds a new dependency; PyYAML is already installed and sufficient for this use case |

**Installation:**
```bash
uv add slowapi
```

## Architecture Patterns

### Recommended Project Structure
```
relay/
  config.yaml                      # Development defaults (checked in)
  cli.py                           # Loads config, passes to app factory
  app/
    config.py                      # RelayConfig dataclass, load_config(), get_config()
    main.py                        # create_relay_app() with lifespan, SlowAPI setup
    rate_limit.py                  # Limiter instance, custom key_func, exception handler
    services/
      mount_registry.py            # Extended: agent_ip, expires_at on MountRecord
      ttl_sweep.py                 # Background TTL sweep coroutine
    routers/
      agent_ws.py                  # @limiter.limit for mount reg, TTL param, per-IP cap
      mount_proxy.py               # @limiter.limit for proxy requests
  templates/
    rate_limited.html              # Styled 429 error page
```

### Pattern 1: SlowAPI Integration with FastAPI
**What:** Initialize a global Limiter with custom key function, attach to app state, register custom exception handler, apply per-route decorators.
**When to use:** Every rate-limited endpoint.
**Example:**
```python
# relay/app/rate_limit.py
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response

def get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or fall back to direct connection.

    Matches existing pattern at mount_proxy.py:85-88.
    """
    forwarded: str | None = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    raise ValueError("Cannot determine client IP from request")

limiter = Limiter(
    key_func=get_client_ip,
    strategy="moving-window",
    headers_enabled=True,      # Adds X-RateLimit-*, Retry-After headers
)

# In route file:
from relay.app.rate_limit import limiter

@router.api_route("/m/{code}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@limiter.limit("300/minute")
async def proxy_request(request: Request, code: str, path: str) -> Response:
    ...
```

### Pattern 2: Custom 429 Exception Handler (HTML vs JSON)
**What:** A single exception handler that inspects the request Accept header to decide between HTML (browser) and JSON (agent) responses.
**When to use:** Registered once on the app via `app.add_exception_handler(RateLimitExceeded, handler)`.
**Example:**
```python
# relay/app/rate_limit.py
import logging
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("relay.ratelimit")

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Return styled HTML for browsers, JSON for API/agent clients."""
    retry_after: int = int(exc.detail.split()[-1]) if exc.detail else 60
    # Extract from headers if available
    client_ip = get_client_ip(request)
    logger.warning("Rate limited: client=%s path=%s", client_ip, request.url.path)

    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return templates.TemplateResponse(
            request, "rate_limited.html",
            context={"retry_after": retry_after},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )
```

### Pattern 3: FastAPI Lifespan for Background Sweep
**What:** Use `asynccontextmanager` lifespan to start/stop the TTL background sweep task.
**When to use:** In `create_relay_app()` to manage the sweep lifecycle.
**Example:**
```python
# relay/app/main.py
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch TTL sweep as background task
    sweep_task = asyncio.create_task(run_ttl_sweep(get_registry(), get_config()))
    yield
    # Shutdown: cancel sweep
    sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Network File Server Relay", lifespan=lifespan)
```

### Pattern 4: Config Module with YAML + Env Var Override
**What:** A `RelayConfig` dataclass loaded from `relay/config.yaml` with env vars overriding individual fields.
**When to use:** All relay configuration. Replaces scattered `os.environ.get()` calls.
**Example:**
```python
# relay/app/config.py
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import yaml

class RelayEnv(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

@dataclass(frozen=True)
class RelayConfig:
    env: RelayEnv
    allowed_origins: list[str]
    mount_reg_rate: str          # "5/hour"
    proxy_request_rate: str      # "300/minute"
    max_ttl_seconds: int         # 86400
    max_mounts_per_ip: int       # 5
    ttl_sweep_interval_seconds: int  # 45

def load_config(config_path: Path) -> RelayConfig:
    """Load config from YAML file, with env var overrides."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    env_str = os.environ.get("RELAY_ENV", raw.get("env", "development"))
    # ... env var overrides for each field ...
    return RelayConfig(env=RelayEnv(env_str), ...)
```

### Pattern 5: Per-IP Mount Cap via Registry Query
**What:** Before registering a new mount, query the registry for active mounts with the same agent IP. Reject if at cap.
**When to use:** In `agent_ws.py` before `registry.register()`.
**Example:**
```python
# relay/app/services/mount_registry.py
def count_mounts_by_ip(self, agent_ip: str) -> int:
    """Count active (non-expired) mounts registered by this IP."""
    return sum(
        1 for m in self._mounts.values()
        if m.agent_ip == agent_ip and m.status != MountStatus.EXPIRED
    )
```

### Anti-Patterns to Avoid
- **Applying rate limit decorator below the route decorator:** SlowAPI requires the `@limiter.limit()` decorator to be BELOW `@router.api_route()` / `@router.get()` -- not above it. The route decorator must be on top.
- **Forgetting `request: Request` parameter:** SlowAPI requires the endpoint to have an explicit `request: Request` parameter or it silently fails to rate limit.
- **Using `get_remote_address` instead of custom key_func:** The built-in `get_remote_address` reads `request.client.host` which behind Cloud Run's proxy gives the load balancer IP, not the real client. Must use X-Forwarded-For.
- **Storing TTL only on agent side:** The agent already has client-side TTL countdown, but a malicious agent could ignore it. Server-side enforcement via the background sweep is essential.
- **Blocking the event loop in the sweep:** The TTL sweep must use `await asyncio.sleep()` and async WebSocket close operations. No blocking I/O.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit tracking | Custom counter dict with timestamp management | SlowAPI + limits library | Sliding window algorithms have subtle edge cases (clock skew, atomic operations, window boundary handling) |
| Rate limit string parsing | Manual "5/hour" parser | limits library `parse()` | Supports all time units, stacked limits, proven parser |
| Retry-After header | Manual calculation | SlowAPI `headers_enabled=True` | Automatically computes and attaches Retry-After based on window stats |
| YAML parsing | Custom config file parser | PyYAML `safe_load()` | Standard, already installed, handles all YAML types safely |

**Key insight:** Rate limiting appears simple but has many edge cases -- atomic counter operations, window boundary precision, header computation, concurrent request handling. SlowAPI handles these through the battle-tested `limits` library.

## Common Pitfalls

### Pitfall 1: SlowAPI Decorator Order with FastAPI
**What goes wrong:** Rate limiting silently doesn't work -- no 429s ever returned.
**Why it happens:** If `@limiter.limit()` is placed above `@router.api_route()`, SlowAPI never intercepts the request.
**How to avoid:** Always place the route decorator first (outermost), then the limit decorator below it.
**Warning signs:** Tests pass for happy path but rate limit tests always get 200 instead of 429.

### Pitfall 2: WebSocket Endpoints Not Rate-Limitable by SlowAPI
**What goes wrong:** SlowAPI's `@limiter.limit()` decorator works on HTTP endpoints but NOT on WebSocket endpoints (it depends on the Request object and HTTP response cycle).
**Why it happens:** WebSocket upgrade is not a normal HTTP request/response -- it cannot return 429 after upgrade.
**How to avoid:** For the agent WebSocket endpoint (`/agent/ws`), perform rate limit checking manually BEFORE accepting the WebSocket. Use the `limits` library directly to `hit()` the rate limit, and if exceeded, close the WebSocket immediately with an error control message. Alternatively, add a separate HTTP registration endpoint that is rate-limited, then the WebSocket connects after approval.
**Warning signs:** `@limiter.limit()` on a `@router.websocket()` endpoint raises errors or silently passes all requests.

### Pitfall 3: X-Forwarded-For Spoofing
**What goes wrong:** An attacker sends a fake `X-Forwarded-For` header to bypass rate limits.
**Why it happens:** Without proxy trust configuration, any client can set X-Forwarded-For.
**How to avoid:** Cloud Run always sets X-Forwarded-For reliably -- the outermost value is the real client IP. In development, fall back to `request.client.host`. The uvicorn `--proxy-headers` and `forwarded_allow_ips="*"` (already configured) mean Starlette trusts X-Forwarded-For, which is correct for Cloud Run where the proxy is trusted.
**Warning signs:** Rate limits applying to wrong IPs in production.

### Pitfall 4: TTL Query Param on WebSocket URL
**What goes wrong:** WebSocket query parameters are not automatically parsed by FastAPI's `Query()` for WebSocket routes.
**Why it happens:** FastAPI WebSocket routes use `Query()` parameters just like HTTP routes, but the behavior can be surprising with type conversion.
**How to avoid:** Declare `ttl: int | None = Query(None)` explicitly in the WebSocket handler signature, same as the existing `code` parameter. Validate that the value is positive and does not exceed the configured max.
**Warning signs:** TTL always None despite being in the URL.

### Pitfall 5: Background Sweep Race with WebSocket Disconnect Handler
**What goes wrong:** The TTL sweep marks a mount EXPIRED and closes the WebSocket, but the `agent_ws.py` finally block also calls `registry.deregister()`. If both run concurrently, double-deregister causes MountNotFoundError.
**Why it happens:** The sweep and the disconnect handler race on cleanup.
**How to avoid:** Make `deregister()` idempotent (don't raise on missing code) or use the existing try/except MountNotFoundError pattern in the finally block (already present). The sweep should mark EXPIRED and close the WebSocket; the disconnect handler in agent_ws already catches MountNotFoundError on deregister.
**Warning signs:** Sporadic MountNotFoundError in logs during TTL expiry.

### Pitfall 6: Config Migration Breaking Existing Deployments
**What goes wrong:** Existing Cloud Run deployment uses RELAY_ENV and RELAY_ALLOWED_ORIGINS env vars. After migration to config.yaml, these stop working if env var override logic has bugs.
**Why it happens:** Config module doesn't properly check env vars or uses wrong names.
**How to avoid:** Keep the SAME env var names (RELAY_ENV, RELAY_ALLOWED_ORIGINS) as overrides. The config module should first load YAML defaults, then override with any matching env vars. Test with both YAML-only and env-var-override scenarios.
**Warning signs:** Relay crashes on startup in production with "RELAY_ALLOWED_ORIGINS must be set" despite being set.

## Code Examples

### SlowAPI Setup in App Factory
```python
# Source: SlowAPI docs + project codebase analysis
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from relay.app.rate_limit import get_client_ip, rate_limit_exceeded_handler

limiter = Limiter(
    key_func=get_client_ip,
    strategy="moving-window",
    headers_enabled=True,
)

# In create_relay_app():
application.state.limiter = limiter
application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

### Rate Limit Decorator on Proxy Route
```python
# Source: SlowAPI docs
from relay.app.rate_limit import limiter

@router.api_route("/m/{code}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@limiter.limit(lambda: get_config().proxy_request_rate)
async def proxy_request(request: Request, code: str, path: str) -> Response:
    ...
```

### Manual Rate Limit Check for WebSocket (Mount Registration)
```python
# Source: limits library API + SlowAPI internals analysis
from limits import parse as parse_limit
from limits import strategies, storage

# Use limits directly for WebSocket rate checking since SlowAPI decorators
# don't work on WebSocket endpoints
_storage = storage.MemoryStorage()
_moving_window = strategies.MovingWindowRateLimiter(_storage)

async def agent_websocket(websocket: WebSocket, code: str | None = Query(None), ttl: int | None = Query(None)) -> None:
    client_ip = websocket.headers.get("x-forwarded-for", websocket.client.host if websocket.client else "unknown")

    # Check mount registration rate limit
    config = get_config()
    mount_limit = parse_limit(config.mount_reg_rate)
    if not _moving_window.test(mount_limit, "mount_reg", client_ip):
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Rate limit exceeded", "retry_after": 3600})
        await websocket.close(code=1008)
        return

    # Check per-IP mount cap
    registry = get_registry()
    if registry.count_mounts_by_ip(client_ip) >= config.max_mounts_per_ip:
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Too many active mounts", "max": config.max_mounts_per_ip})
        await websocket.close(code=1008)
        return

    # Hit the rate limit counter (consume one token)
    _moving_window.hit(mount_limit, "mount_reg", client_ip)

    await websocket.accept()
    # ... rest of handler ...
```

### TTL Background Sweep
```python
# Source: asyncio patterns + project codebase
import asyncio
import logging
import time

logger = logging.getLogger("relay.ttl_sweep")

async def run_ttl_sweep(registry: MountRegistry, config: RelayConfig) -> None:
    """Periodically check all mounts and expire those past their TTL."""
    while True:
        await asyncio.sleep(config.ttl_sweep_interval_seconds)
        now = time.monotonic()
        for code, record in list(registry._mounts.items()):
            if record.expires_at is not None and now >= record.expires_at and record.status == MountStatus.ONLINE:
                # Send warning if close to expiry (handled earlier in the sweep cycle)
                logger.info("TTL expired: code=%s", code)
                record.status = MountStatus.EXPIRED
                await record.connection.close()
```

### Config YAML Schema
```yaml
# relay/config.yaml -- development defaults
env: development
allowed_origins: []     # Empty means wildcard in dev; must be set in production

rate_limits:
  mount_registration: "5/hour"
  proxy_requests: "300/minute"
  max_mounts_per_ip: 5

ttl:
  max_seconds: 86400       # 24 hours
  sweep_interval_seconds: 45
  warning_before_seconds: 300
```

### MountRecord with TTL Fields
```python
# Source: project codebase extension
import time

@dataclass
class MountRecord:
    code: str
    connection: "TunnelConnection"
    status: MountStatus
    agent_ip: str
    created_at: float        # time.monotonic()
    expires_at: float | None  # None means no TTL (up to max enforcement)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `asynccontextmanager` lifespan | FastAPI 0.100+ | Must use lifespan for background sweep startup/shutdown |
| Scattered env vars | Structured config module | This phase | All relay config centralized in config.yaml + env var overrides |
| Client-side TTL only | Server-side TTL enforcement | This phase | Relay controls TTL regardless of agent behavior |
| No rate limiting | SlowAPI in-memory rate limits | This phase | Protects against resource exhaustion |

**Deprecated/outdated:**
- `@app.on_event("startup")`/`@app.on_event("shutdown")`: Replaced by lifespan in modern FastAPI. The current codebase doesn't use either pattern yet, so adopting lifespan is clean.

## Open Questions

1. **SlowAPI decorator on WebSocket endpoints**
   - What we know: SlowAPI's `@limiter.limit()` works on HTTP endpoints but WebSocket endpoints don't follow normal request/response cycle
   - What's unclear: Whether SlowAPI handles the pre-upgrade HTTP request for WebSocket endpoints
   - Recommendation: Use `limits` library directly for WebSocket rate checking (manual `test()` + `hit()`) rather than relying on decorator. This is more explicit and avoids surprises. Code example provided above.

2. **RateLimitExceeded exception retry_after extraction**
   - What we know: The `exc.detail` string contains the rate limit info; SlowAPI uses `headers_enabled` to add Retry-After header
   - What's unclear: Exact format of `exc.detail` and whether retry_after is directly accessible as an attribute
   - Recommendation: In custom exception handler, parse retry info from the response headers that SlowAPI would have set, or compute from window stats. Test during implementation.

3. **Config validation timing**
   - What we know: Config needs validation (e.g., allowed_origins must be set in production)
   - What's unclear: Whether to validate on load or lazily
   - Recommendation: Validate eagerly on startup in `load_config()`. Fail fast with clear error messages. This matches the existing pattern where `create_relay_app()` raises ValueError for missing RELAY_ALLOWED_ORIGINS in production.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/relay/ -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ABUSE-01 | Mount registration rate-limited to 5/hr per IP | integration | `uv run pytest tests/relay/test_rate_limit.py::test_mount_reg_rate_limit -x` | No -- Wave 0 |
| ABUSE-02 | Proxy requests rate-limited to 300/min per IP | integration | `uv run pytest tests/relay/test_rate_limit.py::test_proxy_rate_limit -x` | No -- Wave 0 |
| ABUSE-03 | Max mount TTL enforced (24h default) | unit + integration | `uv run pytest tests/relay/test_ttl.py -x` | No -- Wave 0 |
| ABUSE-04 | Max concurrent mounts per IP capped | unit + integration | `uv run pytest tests/relay/test_mount_cap.py -x` | No -- Wave 0 |
| ABUSE-05 | 429 response with Retry-After header | integration | `uv run pytest tests/relay/test_rate_limit.py::test_429_retry_after -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/relay/ -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/relay/test_rate_limit.py` -- covers ABUSE-01, ABUSE-02, ABUSE-05 (rate limit integration tests)
- [ ] `tests/relay/test_ttl.py` -- covers ABUSE-03 (TTL enforcement and background sweep tests)
- [ ] `tests/relay/test_mount_cap.py` -- covers ABUSE-04 (per-IP mount cap tests)
- [ ] `tests/relay/test_config.py` -- covers config module loading, validation, env var override
- [ ] Framework install: `uv add slowapi` -- new dependency

## Sources

### Primary (HIGH confidence)
- [SlowAPI PyPI](https://pypi.org/project/slowapi/) - v0.1.9, MIT license, last release 2024-02-05
- [SlowAPI ReadTheDocs](https://slowapi.readthedocs.io/) - API reference for Limiter constructor, decorators, exception handling
- [SlowAPI GitHub](https://github.com/laurentS/slowapi) - Examples, middleware setup, get_remote_address/get_ipaddr source
- [limits PyPI](https://pypi.org/project/limits/) - v5.8.0, MemoryStorage supports MovingWindowSupport (confirmed via docs)
- [limits ReadTheDocs](https://limits.readthedocs.io/en/stable/quickstart.html) - Strategy classes, rate limit string format, storage backends
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) - asynccontextmanager pattern for startup/shutdown
- Project codebase: relay/app/main.py, relay/app/routers/agent_ws.py, relay/app/routers/mount_proxy.py, relay/app/services/mount_registry.py

### Secondary (MEDIUM confidence)
- [Flask-Limiter Strategies](https://flask-limiter.readthedocs.io/en/stable/strategies.html) - Strategy names ("fixed-window", "moving-window") shared with SlowAPI since both use limits library
- [limits MemoryStorage source](https://limits.readthedocs.io/en/4.x/_modules/limits/storage/memory.html) - Confirmed MemoryStorage implements MovingWindowSupport

### Tertiary (LOW confidence)
- SlowAPI WebSocket support: Not documented. Recommendation to use limits library directly for WebSocket rate checking is based on architectural analysis, not confirmed by official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - SlowAPI and limits are well-documented, versions confirmed on PyPI, MemoryStorage moving-window support verified
- Architecture: HIGH - Integration points clearly identified in existing codebase; patterns follow FastAPI conventions
- Pitfalls: HIGH - WebSocket decorator limitation identified through architectural analysis; X-Forwarded-For pattern already established in codebase
- Config module: MEDIUM - YAML + env var override pattern is straightforward but the exact field naming and validation approach involves design decisions

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days -- all components are stable/mature libraries)
