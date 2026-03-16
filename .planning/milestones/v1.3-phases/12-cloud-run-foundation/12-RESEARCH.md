# Phase 12: Cloud Run Foundation - Research

**Researched:** 2026-03-16
**Domain:** Docker containerization, Cloud Run deployment, structured logging, CORS/cookie security
**Confidence:** HIGH

## Summary

Phase 12 containerizes the relay for Google Cloud Run and fixes three production-blocking security issues: missing `Secure` flag on session cookies behind HTTPS, wildcard CORS origins allowing credential leakage, and `request.url.scheme` not reflecting HTTPS inside the container.

The relay is a FastAPI/uvicorn app. Cloud Run terminates TLS and forwards requests as HTTP with `X-Forwarded-Proto: https` and `X-Forwarded-For` headers. The Docker image needs a two-stage build (Node for React client, Python for relay), and uvicorn must be configured to trust these forwarded headers. No new dependencies are required -- Python's stdlib `logging` module with a custom JSON formatter handles structured logging, and FastAPI's built-in `CORSMiddleware` already supports explicit origin lists with credentials.

**Primary recommendation:** Use a 3-stage Dockerfile (node build, uv install, slim runtime), configure uvicorn with `--proxy-headers --forwarded-allow-ips='*'`, write a custom `logging.Formatter` that emits JSON with `severity` field to stdout, and add relay-level middleware to stamp `; Secure` on proxied `Set-Cookie` headers when `X-Forwarded-Proto` is `https`.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Multi-stage Dockerfile: Node stage builds React frontend, Python stage runs relay
- Base image: `python:3.11-slim` for the runtime stage, `node:20-slim` for the build stage
- Image scope: relay + tunnel packages only (no LAN server)
- Use `uv` inside Docker for dependency installation (consistent with local dev workflow, uses uv.lock for reproducible builds)
- Shell script (`deploy_relay.sh`) that runs `gcloud builds submit` + `gcloud run deploy`
- Service name: `network-relay`, Region: `us-central1`
- `--max-instances=1`, `--allow-unauthenticated`
- CORS: wildcard in dev mode; locked to `RELAY_ALLOWED_ORIGINS` when `RELAY_ENV=production`
- Logging: Python `logging` module everywhere; dev=human-readable, production=JSON with `severity` field
- Cookie Secure flag: based on `X-Forwarded-Proto` header (not RELAY_ENV)
- Health endpoint (`GET /health`): always available
- Suppress uvicorn's default access logs -- use app-level structured logging instead
- Suppress health endpoint logging to avoid Cloud Run liveness probe noise
- Client IP included in proxy request logs (via X-Forwarded-For)
- Events logged: agent connect/disconnect, mount registration/expiry, proxy request summaries (method, path, status, duration, client IP), errors and exceptions with stack traces

### Claude's Discretion
- Exact structured log field names and JSON schema
- Health endpoint response body format beyond required mount count field
- Middleware vs decorator approach for request logging
- How RELAY_ALLOWED_ORIGINS is parsed (comma-separated env var is fine)
- Dockerfile layer caching optimization

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | Relay runs as Docker container on Cloud Run listening on `$PORT` | Multi-stage Dockerfile pattern, `PORT` env var from Cloud Run runtime contract, uvicorn bind to `0.0.0.0:$PORT` |
| DEPLOY-02 | `GET /health` returns 200 with mount count | New FastAPI router, reads `len(_mounts)` from `MountRegistry` singleton |
| DEPLOY-03 | All logging uses structured JSON (severity + message) to stdout | Custom `logging.Formatter` subclass, Cloud Logging JSON field spec, severity mapping |
| DEPLOY-04 | Session cookies set `Secure` flag behind HTTPS | Relay middleware inspects `X-Forwarded-Proto`, rewrites `Set-Cookie` headers from proxied responses |
| DEPLOY-05 | CORS allows only configured origins with `allow_credentials=True` | `CORSMiddleware` with explicit origin list, env var parsing |
| DEPLOY-06 | uvicorn `--proxy-headers` so `request.url.scheme` reflects HTTPS | uvicorn `proxy_headers=True` + `forwarded_allow_ips="*"` for Cloud Run |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | Web framework (already in project) | Already used by relay |
| uvicorn[standard] | >=0.34.0 | ASGI server (already in project) | Already used, has proxy-headers support |
| Python `logging` | stdlib | Structured logging | No new dependency; user decision |
| Docker | multi-stage | Container build | Cloud Run requirement |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uv` | latest (in Docker) | Dependency installation inside container | Dockerfile build stage |
| `gcloud` CLI | latest | Cloud Run deployment | Deploy script |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom JSON formatter | `python-json-logger` PyPI package | Adds a dependency for ~30 lines of custom code; stdlib is sufficient |
| `google-cloud-logging` library | Custom stdout JSON | Adds heavy GCP SDK dependency; Cloud Run auto-parses JSON from stdout |

**Installation:**
No new Python dependencies required. Docker and gcloud CLI are external tools.

## Architecture Patterns

### Recommended Project Structure
```
Dockerfile                     # Multi-stage: node build -> uv install -> slim runtime
.dockerignore                  # Exclude .git, node_modules, __pycache__, .planning, tests
deploy_relay.sh                # gcloud builds submit + gcloud run deploy
relay/
  app/
    main.py                    # Updated: conditional CORS, health router, logging setup
    logging.py                 # NEW: CloudJsonFormatter + configure_logging()
    routers/
      health.py                # NEW: GET /health endpoint
    middleware/
      secure_cookies.py        # NEW: Stamps Secure on Set-Cookie behind HTTPS
  cli.py                       # Updated: reads PORT env var, proxy-headers, logging config
```

### Pattern 1: Multi-Stage Dockerfile with uv
**What:** 3-stage build -- Node builds React SPA, Python installs relay dependencies, slim runtime copies artifacts.
**When to use:** Always for this project (user decision).
**Example:**
```dockerfile
# Source: https://docs.astral.sh/uv/guides/integration/docker/
# Stage 1: Build React client
FROM node:20-slim AS client-builder
WORKDIR /build
COPY client/package.json client/package-lock.json ./
RUN npm ci --silent
COPY client/ ./
RUN npm run build

# Stage 2: Install Python dependencies with uv
FROM python:3.11-slim AS python-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
# Install deps first (layer cache)
RUN uv sync --locked --no-install-project --no-dev
COPY relay/ relay/
COPY tunnel/ tunnel/
RUN uv sync --locked --no-editable --no-dev

# Stage 3: Slim runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=python-builder /app/.venv /app/.venv
COPY --from=client-builder /build/dist /app/client/dist
COPY relay/templates /app/relay/templates
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"
CMD ["uvicorn", "relay.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Pattern 2: Conditional CORS Based on Environment
**What:** Wildcard origins in dev, explicit origin list in production with `allow_credentials=True`.
**When to use:** When `RELAY_ENV=production`.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/cors/
import os

relay_env = os.environ.get("RELAY_ENV", "development")

if relay_env == "production":
    raw_origins = os.environ.get("RELAY_ALLOWED_ORIGINS", "")
    if not raw_origins:
        raise ValueError("RELAY_ALLOWED_ORIGINS must be set when RELAY_ENV=production")
    origins = [o.strip() for o in raw_origins.split(",")]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### Pattern 3: Cloud Logging JSON Formatter
**What:** Custom `logging.Formatter` that outputs JSON with `severity` field to stdout.
**When to use:** When `RELAY_ENV=production`.
**Example:**
```python
# Source: https://cloud.google.com/logging/docs/structured-logging
import json
import logging
import traceback

# Cloud Logging severity values (maps Python level names)
_SEVERITY_MAP: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}

class CloudJsonFormatter(logging.Formatter):
    """JSON formatter for Google Cloud Logging structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, object] = {
            "severity": _SEVERITY_MAP.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": self.formatTime(record, self.datefmt),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["stack_trace"] = traceback.format_exception(*record.exc_info)
        # Merge any extra fields attached to the record
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)
        return json.dumps(log_entry, default=str)
```

### Pattern 4: Secure Cookie Middleware
**What:** ASGI middleware that adds `; Secure` to `Set-Cookie` headers when request arrived over HTTPS.
**When to use:** Always in production behind TLS-terminating proxy.
**Example:**
```python
from starlette.types import ASGIApp, Receive, Scope, Send

class SecureCookieMiddleware:
    """Stamps Secure flag on Set-Cookie headers when X-Forwarded-Proto is https."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check X-Forwarded-Proto from request headers
        headers = dict(scope.get("headers", []))
        proto = headers.get(b"x-forwarded-proto", b"").decode()
        is_https = proto == "https"

        async def send_wrapper(message: dict) -> None:
            if is_https and message["type"] == "http.response.start":
                new_headers = []
                for key, value in message.get("headers", []):
                    if key.lower() == b"set-cookie" and b"secure" not in value.lower():
                        value = value + b"; Secure"
                    new_headers.append((key, value))
                message = {**message, "headers": new_headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

### Pattern 5: Health Endpoint
**What:** Simple GET endpoint returning mount count.
**When to use:** Cloud Run liveness probes.
**Example:**
```python
from fastapi import APIRouter
from relay.app.services.mount_registry import get_registry

router = APIRouter()

@router.get("/health")
def health_check() -> dict[str, object]:
    registry = get_registry()
    return {"status": "ok", "mounts": len(registry._mounts)}
```

### Anti-Patterns to Avoid
- **Wildcard CORS with `allow_credentials=True`:** Browsers refuse this combination per CORS spec; Starlette/FastAPI will raise an error. Must use explicit origin list when credentials are enabled.
- **Hardcoding port 8080:** Cloud Run injects `PORT` env var. Always read from env, defaulting to 8080.
- **`forwarded_allow_ips` defaulting to 127.0.0.1:** Cloud Run's load balancer connects from internal IPs, not 127.0.0.1. Must set `forwarded_allow_ips="*"` or use `FORWARDED_ALLOW_IPS` env var.
- **Using `google-cloud-logging` library:** Adds heavy dependency. Cloud Run auto-parses JSON from stdout -- just write structured JSON.
- **Logging health check requests:** Cloud Run sends frequent liveness probes that create noise. Filter `/health` from request logging.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CORS handling | Custom header middleware | FastAPI `CORSMiddleware` | Handles preflight OPTIONS, credential headers, Vary correctly |
| Proxy header parsing | Custom X-Forwarded-* extraction | uvicorn `--proxy-headers` | Handles X-Forwarded-Proto, X-Forwarded-For, edge cases |
| Docker layer caching | Manual dependency management | uv `--no-install-project` then `--no-editable` | Built-in two-pass install for optimal caching |

**Key insight:** The security fixes are all about correctly configuring existing middleware/tools, not building custom solutions. The only custom code needed is the JSON log formatter (~30 lines) and the Secure cookie middleware (~20 lines).

## Common Pitfalls

### Pitfall 1: uvicorn forwarded-allow-ips Defaults to 127.0.0.1
**What goes wrong:** Proxy headers are silently ignored because Cloud Run's load balancer IP is not 127.0.0.1.
**Why it happens:** uvicorn default for `--forwarded-allow-ips` is `127.0.0.1` -- requests from Cloud Run's internal LB are rejected as untrusted.
**How to avoid:** Set `forwarded_allow_ips="*"` when running in Cloud Run (single-instance, behind Google's LB, trusted network).
**Warning signs:** `request.url.scheme` stays `http` even though browser URL is `https`.

### Pitfall 2: Set-Cookie Without Secure Flag Behind HTTPS
**What goes wrong:** Browsers on Chrome 80+ will block cookies without `Secure` flag on HTTPS origins. Session cookies set by the LAN server (proxied through relay) will be silently rejected.
**Why it happens:** The LAN server's `response.set_cookie()` (in `server/app/routers/auth.py`) does not set `secure=True` because LAN access is plain HTTP. When proxied through the relay behind Cloud Run's HTTPS, the cookie needs the `Secure` flag.
**How to avoid:** Relay-level middleware that inspects `X-Forwarded-Proto` and appends `; Secure` to `Set-Cookie` headers in proxied responses. This is correct because the relay is the component that knows the external protocol.
**Warning signs:** Login fails silently in production -- password accepted but subsequent requests are unauthenticated (cookie rejected by browser).

### Pitfall 3: CORSMiddleware Wildcard + allow_credentials
**What goes wrong:** Starlette raises an error: cannot use `allow_origins=["*"]` with `allow_credentials=True`.
**Why it happens:** CORS spec forbids wildcard origin with credentials -- browser would ignore the response.
**How to avoid:** In production, always use explicit origin list. Dev mode can use wildcard but without `allow_credentials`.
**Warning signs:** Import error or 500 on startup.

### Pitfall 4: uv symlinks in Docker Multi-Stage Builds
**What goes wrong:** Packages installed in builder stage create symlinks that break when copied to runtime stage.
**Why it happens:** `uv` defaults to `UV_LINK_MODE=symlink` for performance; symlinks point to builder paths that don't exist in runtime stage.
**How to avoid:** Set `ENV UV_LINK_MODE=copy` in the builder stage.
**Warning signs:** `ImportError` or `ModuleNotFoundError` at container startup -- works in builder, breaks in runtime.

### Pitfall 5: Container Listening on 127.0.0.1
**What goes wrong:** Cloud Run health checks fail, container marked unhealthy, deployment fails.
**Why it happens:** Some frameworks default to localhost binding.
**How to avoid:** Always bind to `0.0.0.0` (uvicorn's `--host 0.0.0.0`).
**Warning signs:** Deployment timeout with "Container failed to start and listen on the port defined by the PORT environment variable."

### Pitfall 6: Missing relay/templates in Docker Image
**What goes wrong:** Jinja2 `TemplateNotFoundError` at runtime when accessing landing page or error pages.
**Why it happens:** Templates are in `relay/templates/` but if only Python packages are copied via venv, templates are missed.
**How to avoid:** Explicitly `COPY relay/templates /app/relay/templates` in Dockerfile, since templates are not part of the installed Python package.
**Warning signs:** 500 error on first request to `/` or any mount error page.

## Code Examples

### Configuring Logging (dev vs production)
```python
# relay/app/logging.py
import json
import logging
import sys
import traceback
from enum import Enum


class RelayEnv(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


_SEVERITY_MAP: dict[str, str] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


class CloudJsonFormatter(logging.Formatter):
    """Emits one JSON object per line with a 'severity' field for Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "severity": _SEVERITY_MAP.get(record.levelname, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(entry, default=str)


def configure_logging(env: RelayEnv) -> None:
    """Set up root logger for the relay."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if env == RelayEnv.PRODUCTION:
        handler.setFormatter(CloudJsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))

    root.addHandler(handler)

    # Suppress uvicorn access logs -- relay does its own request logging
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
```

### uvicorn Startup with Proxy Headers and PORT
```python
# relay/cli.py (updated)
import os
import uvicorn

def main() -> None:
    # ... argparse setup ...
    port = int(os.environ.get("PORT", "8001"))
    relay_env = os.environ.get("RELAY_ENV", "development")

    configure_logging(RelayEnv(relay_env))

    uvicorn.run(
        "relay.app.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,   # Suppress uvicorn default access log
        log_config=None,     # Don't override our logging config
    )
```

### Deploy Script
```bash
#!/usr/bin/env bash
# deploy_relay.sh — Build and deploy relay to Cloud Run
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="us-central1"
SERVICE="network-relay"
ALLOWED_ORIGINS="${RELAY_ALLOWED_ORIGINS:?Set RELAY_ALLOWED_ORIGINS}"

echo "Building container image..."
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE"

echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --image "gcr.io/$PROJECT_ID/$SERVICE" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --max-instances 1 \
  --set-env-vars "RELAY_ENV=production,RELAY_ALLOWED_ORIGINS=$ALLOWED_ORIGINS" \
  --session-affinity
```

### .dockerignore
```
.git
.planning
.claude
__pycache__
*.pyc
.pytest_cache
.ruff_cache
node_modules
client/node_modules
tests
server/tests
docs
feature-ideas
*.md
!relay/templates/*.html
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pip install` in Docker | `uv sync --locked` in Docker | 2024-2025 | Faster builds, lockfile reproducibility |
| `google-cloud-logging` SDK | JSON to stdout | 2022+ | No SDK dependency, Cloud Run auto-parses JSON from stdout |
| Manual CORS headers | FastAPI `CORSMiddleware` | Always | Handles preflight, Vary, credential edge cases |
| `--forwarded-allow-ips 127.0.0.1` | `--forwarded-allow-ips *` in Cloud Run | N/A | Required for Cloud Run where LB IP is not localhost |

**Deprecated/outdated:**
- `google-cloud-logging` Python library for Cloud Run: unnecessary overhead; stdout JSON is the recommended approach for managed services

## Open Questions

1. **Relay template path resolution in Docker**
   - What we know: `relay/app/routers/landing.py` resolves templates via `Path(__file__).resolve().parent.parent.parent / "templates"`. In Docker, the venv copy may change `__file__` location.
   - What's unclear: Whether `--no-editable` install changes `__file__` resolution for the relay package.
   - Recommendation: Test template resolution in Docker build during Plan 12-01. If broken, add explicit `COPY relay/templates` and update template path to use env var or fixed path.

2. **Cloud Run request timeout for WebSocket agent connections**
   - What we know: Cloud Run default request timeout is 300 seconds. Agent WebSocket connections need to persist much longer.
   - What's unclear: Whether `--timeout` flag is needed in deploy script.
   - Recommendation: Set `--timeout 3600` (1 hour) in deploy script for WebSocket connections. Cloud Run supports up to 3600s for streaming requests.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/relay/ -x` |
| Full suite command | `uv run pytest tests/relay/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-01 | Container starts on $PORT, serves requests | smoke | Manual: `docker build . && docker run -e PORT=8080 -p 8080:8080` then `curl localhost:8080/health` | N/A (manual) |
| DEPLOY-02 | GET /health returns 200 with mount count | unit | `uv run pytest tests/relay/test_health.py -x` | Wave 0 |
| DEPLOY-03 | Structured JSON logging with severity field | unit | `uv run pytest tests/relay/test_logging.py -x` | Wave 0 |
| DEPLOY-04 | Set-Cookie carries Secure flag behind HTTPS | unit | `uv run pytest tests/relay/test_secure_cookies.py -x` | Wave 0 |
| DEPLOY-05 | CORS rejects unlisted origins, allows listed | unit | `uv run pytest tests/relay/test_cors.py -x` | Wave 0 |
| DEPLOY-06 | request.url.scheme reflects https with proxy headers | unit | `uv run pytest tests/relay/test_proxy_headers.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/relay/ -x`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/relay/test_health.py` -- covers DEPLOY-02
- [ ] `tests/relay/test_logging.py` -- covers DEPLOY-03 (verify JSON format, severity mapping)
- [ ] `tests/relay/test_secure_cookies.py` -- covers DEPLOY-04 (verify Secure flag added when X-Forwarded-Proto: https)
- [ ] `tests/relay/test_cors.py` -- covers DEPLOY-05 (verify preflight rejection for unlisted origins)
- [ ] `tests/relay/test_proxy_headers.py` -- covers DEPLOY-06 (verify request.url.scheme with proxy headers)

## Sources

### Primary (HIGH confidence)
- [Cloud Run container runtime contract](https://docs.cloud.google.com/run/docs/container-contract) -- PORT env var, TLS termination, 0.0.0.0 binding requirement
- [Cloud Logging structured logging](https://docs.cloud.google.com/logging/docs/structured-logging) -- JSON field spec, severity field recognition
- [uv Docker integration guide](https://docs.astral.sh/uv/guides/integration/docker/) -- Multi-stage build pattern, UV_LINK_MODE, --no-editable
- [Uvicorn settings](https://uvicorn.dev/settings/) -- proxy-headers, forwarded-allow-ips, access_log configuration
- [FastAPI CORS tutorial](https://fastapi.tiangolo.com/tutorial/cors/) -- CORSMiddleware configuration, wildcard+credentials restriction

### Secondary (MEDIUM confidence)
- [Cloud Run WebSockets documentation](https://docs.cloud.google.com/run/docs/triggering/websockets) -- WebSocket support, session affinity
- [Cloud Functions request headers](https://docs.cloud.google.com/functions/docs/reference/headers) -- X-Forwarded-Proto, X-Forwarded-For headers (Cloud Functions = Cloud Run functions)

### Tertiary (LOW confidence)
- gcloud deploy command flags -- verified against official docs but exact session-affinity flag syntax should be confirmed at deploy time

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing tools
- Architecture: HIGH -- patterns verified against official docs (Cloud Run, uv Docker, uvicorn)
- Pitfalls: HIGH -- verified against official docs and known failure modes
- Cookie security: HIGH -- confirmed `set_cookie()` in auth.py lacks `secure=True`, relay proxy passes Set-Cookie headers verbatim
- Structured logging: HIGH -- Cloud Logging JSON field spec verified from official docs

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (stable domain, 30-day validity)
