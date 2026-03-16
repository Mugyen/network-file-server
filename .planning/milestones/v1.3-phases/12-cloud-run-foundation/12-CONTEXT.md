# Phase 12: Cloud Run Foundation - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Dockerize the relay, add health check and structured logging, fix HTTPS cookie/CORS/proxy-header security bugs. The relay runs as a deployable Docker container on Cloud Run with all production-blocking security bugs fixed.

</domain>

<decisions>
## Implementation Decisions

### Docker build approach
- Multi-stage Dockerfile: Node stage builds React frontend, Python stage runs relay
- Base image: `python:3.11-slim` for the runtime stage, `node:20-slim` for the build stage
- Image scope: relay + tunnel packages only (no LAN server)
- Use `uv` inside Docker for dependency installation (consistent with local dev workflow, uses uv.lock for reproducible builds)

### Deploy workflow
- Shell script (`deploy_relay.sh`) that runs `gcloud builds submit` + `gcloud run deploy`
- Consistent with existing `run_relay.sh` pattern
- Service name: `network-relay`
- Region: `us-central1`
- `--max-instances=1` (relay is stateful — WebSocket connections + in-memory state)
- `--allow-unauthenticated` (public service)
- Env vars hardcoded in script with sensible defaults (RELAY_ENV, RELAY_ALLOWED_ORIGINS)

### Dev vs production mode
- CORS: wildcard `allow_origins=["*"]` in dev mode; locked to `RELAY_ALLOWED_ORIGINS` when `RELAY_ENV=production`
- Logging: Python `logging` module everywhere; dev mode uses human-readable text formatter, production uses JSON formatter with `severity` field
- Cookie Secure flag: based on `X-Forwarded-Proto` header (not RELAY_ENV) — works behind any TLS-terminating proxy
- Health endpoint (`GET /health`): always available in both dev and production

### Logging scope
- Events logged: agent connect/disconnect, mount registration/expiry, proxy request summaries (method, path, status, duration, client IP), errors and exceptions with stack traces
- Suppress uvicorn's default access logs — use app-level structured logging instead
- Suppress health endpoint logging to avoid Cloud Run liveness probe noise
- Client IP included in proxy request logs (via X-Forwarded-For)

### Claude's Discretion
- Exact structured log field names and JSON schema
- Health endpoint response body format beyond required mount count field
- Middleware vs decorator approach for request logging
- How RELAY_ALLOWED_ORIGINS is parsed (comma-separated env var is fine)
- Dockerfile layer caching optimization

</decisions>

<specifics>
## Specific Ideas

- Deploy script should mirror the pattern of `run_relay.sh` — simple, inspectable, no CI dependency
- JSON logging format should use `severity` field (not `level`) for Cloud Logging compatibility
- Dev mode logging should look like standard Python logging (e.g., `INFO     Agent connected: abc123`)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `relay/app/main.py`: FastAPI app factory with CORSMiddleware — needs CORS update
- `relay/cli.py`: CLI entry point with argparse — needs `--proxy-headers` and logging config
- `relay/app/services/mount_registry.py`: MountRegistry with `_mounts` dict — health endpoint can report `len(_mounts)`
- `run_relay.sh`: Existing startup script pattern to mirror for deploy script

### Established Patterns
- App factory pattern (`create_relay_app()`) — health endpoint adds to this
- Router-based organization (`relay/app/routers/`) — health could be a new router or inline
- Module-level singleton for registry (`get_registry()`) — health reads from this

### Integration Points
- `CORSMiddleware` in `create_relay_app()` — replace wildcard with conditional origins
- `uvicorn.run()` in `relay/cli.py` — add `--proxy-headers` and logging config
- `relay/app/routers/agent_ws.py` — add logging for agent connect/disconnect
- `relay/app/routers/mount_proxy.py` — add request logging middleware

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-cloud-run-foundation*
*Context gathered: 2026-03-16*
