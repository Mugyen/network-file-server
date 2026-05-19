# Phase 13: Abuse Prevention - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Rate-limit mount registration and proxy requests, enforce max TTL and per-IP mount cap. External agents cannot exhaust relay resources. No new UI features, no persistence layer, no landing page changes.

</domain>

<decisions>
## Implementation Decisions

### Rate limit error experience
- Browser requests hitting 429 get a styled Jinja2 error page (consistent with existing not_found/offline/expired templates)
- Error page shows the exact retry countdown (driven by Retry-After header value), e.g. "Try again in 45 seconds"
- Agent mount registration failures return JSON `{"error": "...", "retry_after": N}` — agent CLI prints the message and exits (no auto-retry)
- Rate-limited requests logged at WARNING level with client IP for abuse monitoring in Cloud Logging

### Rate limit storage & algorithm
- Sliding window algorithm for both mount registration and proxy request rate limits
- Use SlowAPI library (built on `limits`) — supports sliding window, in-memory storage, Retry-After headers, per-route config
- In-memory storage — counters reset on relay restart, which is acceptable for single-instance Cloud Run
- Client IP extraction via X-Forwarded-For header (consistent with existing mount_proxy.py:85-88 pattern); SlowAPI custom key function

### Mount TTL enforcement
- Agent specifies TTL as query parameter on WebSocket URL: `/agent/ws?code=abc&ttl=3600` (consistent with existing `?code=` pattern)
- Relay caps requested TTL to configured maximum (default 24h) — agent cannot exceed the cap
- On TTL expiry: immediate disconnect — relay marks mount EXPIRED and closes agent WebSocket; browser requests get existing "expired" error page (HTTP 410)
- Relay sends `{"type": "ttl_warning", "expires_in": 300}` control message 5 minutes before expiry so agent can notify user
- Periodic asyncio background sweep (every 30-60s) checks all mounts and disconnects expired ones

### Configurability — config.yaml module
- Create a dedicated config module (`relay/app/config.py`) that loads `relay/config.yaml`
- Single `relay/config.yaml` with development defaults checked into the repo
- Env vars override YAML values (12-factor app style for Cloud Run deployments)
- Absorb all existing relay config into the module: RELAY_ENV, RELAY_ALLOWED_ORIGINS, plus all new rate limit settings
- All rate limit thresholds configurable: mount registration rate (default 5/hr), proxy request rate (default 300/min), max TTL (default 24h), max concurrent mounts per IP (default 5)

### Claude's Discretion
- Exact SlowAPI middleware integration approach (app-level vs per-router)
- Config YAML schema structure and field naming
- Background sweep interval (30s vs 60s)
- How env var names map to YAML keys (e.g., RELAY_RATE_MOUNT_REG or similar)
- Whether to validate config.yaml on startup or lazily

</decisions>

<specifics>
## Specific Ideas

- Config module should handle loading, serialization, and validation — not just a dict wrapper
- The config.yaml approach is preferred over scattered env vars for all relay configuration going forward
- Existing RELAY_ENV and RELAY_ALLOWED_ORIGINS should migrate into config.yaml (env vars still work as overrides)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `relay/app/routers/mount_proxy.py:85-88`: Client IP extraction from X-Forwarded-For — reuse pattern for SlowAPI key function
- `relay/app/enums.py:MountStatus.EXPIRED`: Already exists — TTL enforcement transitions to this status
- `relay/app/exceptions.py:MountExpiredError`: Already exists — raised by `get_connection()` for expired mounts
- `relay/templates/`: Jinja2 error templates (not_found, offline, expired) — add rate_limited.html in same pattern
- `relay/app/services/mount_registry.py`: In-memory registry — TTL sweep reads from this; per-IP mount counting queries this

### Established Patterns
- App factory in `create_relay_app()` — middleware and config loading hooks in here
- Router-based organization (`relay/app/routers/`) — rate limits can be applied per-router
- Singleton registry via `get_registry()` — config module can follow same singleton pattern
- Middleware stacking order: SecureCookieMiddleware (inner), CORSMiddleware (outer) — rate limit middleware placement matters

### Integration Points
- `create_relay_app()` in `relay/app/main.py` — add SlowAPI middleware, config loading, background sweep startup
- `agent_ws.py` `/agent/ws` endpoint — add TTL query param, enforce per-IP mount cap and registration rate limit
- `mount_proxy.py` `/m/{code}/*` endpoint — apply proxy request rate limit
- `relay/cli.py` — load config.yaml path, pass to app factory
- `MountRegistry.register()` — add TTL field to MountRecord, add `created_at`/`expires_at` timestamps
- FastAPI lifespan — start/stop the background TTL sweep task

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-abuse-prevention*
*Context gathered: 2026-03-17*
