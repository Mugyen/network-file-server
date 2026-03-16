# Project Research Summary

**Project:** Network File Server — v1.3 Productionize Friend Tier
**Domain:** Cloud Run hardening of a stateful WebSocket relay + file sharing application
**Researched:** 2026-03-16
**Confidence:** HIGH

## Executive Summary

v1.3 is a productionization milestone for an existing, fully-functional relay tunnel system. The relay (FastAPI + WebSockets) is already shipping and wired up; the problem is it runs on localhost with wildcard CORS, in-memory state that evaporates on restart, and zero abuse prevention. Turning it into a public Cloud Run service requires a well-defined deployment contract (Dockerfile, health check, `$PORT`), three security fixes that must land before any production auth will work (CORS lockdown + cookie Secure flag + proxy header forwarding), and then layered hardening on top. The recommended approach is strictly additive: four new lightweight dependencies (`slowapi`, `aiosqlite`, `structlog`, `pydantic-settings`), no new infrastructure services, and a `--max-instances=1` constraint that simplifies everything from rate limiting to SQLite persistence.

The biggest risk in this milestone is the interaction between Cloud Run's multi-layer proxy model and the existing session cookie mechanism. If uvicorn starts without `--proxy-headers`, all scheme detection is broken (`request.url.scheme` will always be `http` inside the container), which means `Secure` cookies are never set and `allow_credentials=True` combined with `allow_origins=["*"]` causes browsers to silently strip session cookies on every request. These two bugs are invisible in local development and only appear in production — making them the highest-priority items to verify after first deployment. CORS lockdown and proxy headers must be addressed in the same phase as the Dockerfile, not deferred.

The second major risk is the SQLite-on-GCS-FUSE combination. Multiple sources confirm SQLite WAL mode corrupts silently on FUSE-backed filesystems because POSIX byte-range locking is not supported. The mitigation is to use `journal_mode=DELETE` (not WAL) if GCS FUSE is used, or more simply to use `--min-instances=1` with in-container SQLite at `/tmp/mounts.db` and accept that mount codes are lost on redeploy (agents reconnect and reclaim their codes). For a friends-tier service, this tradeoff is correct.

## Key Findings

### Recommended Stack

v1.3 adds exactly four new Python dependencies to the existing stack and changes nothing else. The existing stack (FastAPI, uvicorn, pydantic, bcrypt, itsdangerous, jinja2, aiofiles, websockets, httpx, httpx-ws) is validated and untouched. Per-file TTL deletion uses `asyncio.create_task` (stdlib), not APScheduler. The always-on drop box uses `asyncio.create_subprocess_exec` (stdlib), not a separate container. CORS lockdown and cookie hardening are configuration changes to existing middleware.

**New dependencies for v1.3:**
- `slowapi >=0.1.9`: Per-IP rate limiting on relay endpoints — no Redis required, in-memory counters, integrates via `@limiter.limit()` decorators with `get_remote_address` reading `X-Forwarded-For` correctly for Cloud Run
- `aiosqlite >=0.22.0`: Async SQLite for persistent mount registry — wraps stdlib `sqlite3`, single-table schema, no ORM or migrations framework needed
- `structlog >=25.0.0`: JSON structured logging to stdout for Cloud Run / Cloud Logging ingestion — dev uses `ConsoleRenderer`, production uses `JSONRenderer`, toggled by `RELAY_ENV` env var
- `pydantic-settings >=2.13.0`: Typed env-var config at startup — fail-fast on missing vars, reads `.env` in dev and Cloud Run env vars in production, replaces scattered `os.environ.get()` calls

**What not to add:** Redis (no horizontal scaling needed), Cloud SQL ($50+/month for a 2-column table), APScheduler (alpha in v4; v3 is heavyweight for one-shot fire-and-forget tasks), `google-cloud-logging` SDK (15MB of GCP client libs for a stdout formatter), SQLAlchemy (single-table registry does not benefit from ORM abstraction).

### Expected Features

The features research identifies a clear 4-tier priority structure, with each tier having a hard dependency on the previous one.

**Must have — deploy gate (v1.3 Core):**
- Cloud Run Dockerfile with health check endpoint (`GET /health`), structured logging, and `$PORT` env var support
- HTTPS cookie `Secure` flag via `X-Forwarded-Proto` detection (uvicorn `--proxy-headers` flag)
- CORS lockdown — replace `allow_origins=["*"]` with `RELAY_ALLOWED_ORIGINS` env var

**Must have — hardening (v1.3 Safety Layer):**
- Rate limiting on mount registration (`5/hour` per IP) and proxy requests (`300/min` per IP)
- Mandatory mount TTL enforcement (default 24h, relay-enforced maximum)
- Per-IP concurrent mount cap (default 5 active mounts per IP)

**Should have — persistence (v1.3 Reliability):**
- SQLite persistent mount registry so mount codes survive relay restarts and agents can reclaim their codes

**Should have — polish (v1.3 UX):**
- Relay landing page with OG meta tags for social sharing previews
- Expanded connection status indicator (add "Host Offline" 503 and "Mount Expired" 410 states)
- Default always-on public drop box (relay starts its own internal agent pointing to `/tmp/dropbox/`)
- Per-file upload TTL with auto-deletion and toast notification

**Defer to v2+:**
- Redis (revisit only if scaling past one Cloud Run instance)
- Multi-instance Cloud Run (requires session affinity + distributed rate limiting + multi-writer SQLite replacement)
- E2E encryption (requires browser-side WebAssembly crypto, breaks relay's ability to rewrite headers)
- Custom domains per mount (CNAME + wildcard TLS provisioning = full PaaS scope)
- Per-user accounts on relay (separate milestone, v1.4+)

**Estimated effort:** 28–44 hours total across 4 phases.

### Architecture Approach

The v1.3 architecture is strictly additive. The existing tunnel protocol (binary frames, UUID stream multiplexing, `httpx.ASGITransport`) is untouched. The relay's `create_relay_app()` gains a FastAPI `lifespan` context manager that initializes `MountPersistence` (new), configures SlowAPI middleware, and optionally starts the embedded drop box agent task. The in-memory `MountRegistry` is retained as the runtime source of truth; `MountPersistence` (SQLite) stores mount metadata alongside it for restart recovery. `TunnelConnection` objects are never persisted — they hold live WebSocket state.

**Key components and their v1.3 changes:**
1. `relay/Dockerfile` (NEW) — multi-stage uv build, Cloud Run `$PORT` support, `--proxy-headers` in CMD
2. `relay/app/services/mount_persistence.py` (NEW) — `aiosqlite`-backed mount metadata store, single-table schema
3. `server/app/services/upload_ttl_service.py` (NEW) — asyncio task-based TTL scheduler with strong task references in a module-level set
4. `relay/app/main.py` (MODIFIED) — add `lifespan`, SlowAPI, CORS lockdown, health router, drop box task
5. `relay/app/routers/mount_proxy.py` (MODIFIED) — add `GET /m/{code}/status` for SPA polling
6. `server/app/middleware/auth_middleware.py` (MODIFIED) — `Secure; SameSite=None` cookies when `RELAY_HTTPS=true`
7. React SPA: `ConnectionStatus.tsx` and `useWebSocket.ts` (MODIFIED) — poll `/m/{code}/status`, show 3-state indicator

Connection status UI uses REST polling (`GET /m/{code}/status` every 30s) rather than a dedicated second WebSocket channel. Status changes are rare; 30-second polling lag is acceptable; maintaining a relay-to-browser WebSocket registry would add complexity disproportionate to the benefit.

All production-specific behavior is controlled by environment variables with permissive development defaults. Single-instance Cloud Run (`--max-instances=1`) is the correct deployment model — the relay is inherently stateful and horizontal scaling would require distributed rate limiting, multi-writer SQLite replacement, and sticky session routing.

### Critical Pitfalls

1. **SQLite WAL mode on GCS FUSE corrupts silently** — WAL requires POSIX byte-range locking which GCS FUSE does not provide. Use `journal_mode=DELETE` + `synchronous=FULL` on FUSE mounts, or (preferred for v1.3) use `--min-instances=1` with in-container SQLite at `/tmp/mounts.db` and accept data loss on redeploy. Never use WAL mode on a network filesystem.

2. **uvicorn without `--proxy-headers` breaks HTTPS detection** — Cloud Run terminates TLS at the load balancer; `request.url.scheme` inside the container is always `http` unless uvicorn is started with `--proxy-headers --forwarded-allow-ips='*'`. Without this, `Secure` cookies are never set in production, and `navigator.clipboard` (HTTPS-only browser API) fails. Must be in the Dockerfile CMD.

3. **`allow_origins=["*"]` + `allow_credentials=True` silently strips all session cookies** — The browser rejects this combination per the Fetch spec. Every authenticated request looks unauthenticated. Fix: use an explicit `RELAY_ALLOWED_ORIGINS` list from environment variable whenever credentials are enabled. Test with browser DevTools cookie inspector after first Cloud Run deploy.

4. **Fire-and-forget `asyncio.create_task` for TTL cleanup is silently GC'd** — Python's asyncio event loop holds only a weak reference to tasks. Under memory pressure, the cleanup task disappears with no error, and files accumulate forever. Fix: store all pending tasks in a module-level `set` with a `done_callback` to discard on completion. Prefer a single periodic cleanup loop over per-file tasks.

5. **Reserved drop box code can be hijacked by user agents** — The current `agent_ws.py` allows any agent to request a preferred code. If the drop box agent is momentarily offline during a startup race, a user agent can claim the `dropbox` code. Fix: maintain `RESERVED_CODES = frozenset({"dropbox"})` in relay config and reject external agent registrations for reserved codes with WebSocket close 4009.

## Implications for Roadmap

Based on combined research, the dependency graph and security considerations drive a clear 4-phase structure.

### Phase 1: Cloud Run Foundation

**Rationale:** Everything else runs inside the container or depends on the HTTPS context it provides. CORS and cookie security bugs cannot be tested until the container exists. This phase must land before any production authentication can be validated.
**Delivers:** A deployable Docker image, working health check, structured logging, and three security fixes (proxy headers, CORS lockdown, cookie Secure flag) that unblock all subsequent testing.
**Features addressed:** Cloud Run Dockerfile, health check endpoint, structured logging, CORS lockdown, HTTPS cookie Secure flag.
**Avoids:** Pitfall 6 (uvicorn without `--proxy-headers`), Pitfall 3 (wildcard CORS + credentials), Pitfall 11 (structured log format conflicts with Cloud Run parser), Pitfall 12 (Docker layer cache invalidation).
**Research flag:** Standard patterns — well-documented Cloud Run + FastAPI + uv Docker patterns. No additional research phase needed.

### Phase 2: Abuse Prevention

**Rationale:** The relay has a public surface after Phase 1 deployment. Without rate limiting, mount registration is an open tunnel server any IP can exhaust. This phase hardens the deployed service before adding persistence complexity.
**Delivers:** Per-IP rate limits on agent registration and proxy requests, mandatory mount TTL enforcement, per-IP concurrent mount cap.
**Features addressed:** Rate limiting (mount registration + proxy requests), mandatory mount TTL, max mounts per IP.
**Avoids:** Pitfall 5 (rate limiter per-process — document `--max-instances=1` constraint); in-memory rate limiter state is accepted for v1.3 scope.
**Research flag:** Standard patterns — slowapi integration is well-documented. No additional research needed.

### Phase 3: SQLite Persistent Mount Registry

**Rationale:** Persistence is separated from rate limiting because it introduces the most architectural complexity (lifespan handler, aiosqlite, Cloud Storage volume mount or `/tmp` strategy decision). Doing it after the relay is deployed allows testing the exact container lifecycle behavior before adding SQLite.
**Delivers:** Mount codes that survive relay restarts; agents reconnect and reclaim their codes; mount metadata (TTL, status) persists across cold starts.
**Features addressed:** SQLite persistent mount registry.
**Avoids:** Pitfall 1 (SQLite WAL on GCS FUSE — use `journal_mode=DELETE` or `/tmp` + `--min-instances=1`), Pitfall 2 (drop box startup race — lifespan must await agent registration before health check passes).
**Research flag:** Needs validation during implementation — the GCS FUSE vs `/tmp` + `--min-instances=1` storage strategy decision depends on acceptable data loss semantics for the specific deployment. Test full cold-start cycle in staging before committing.

### Phase 4: UX Polish

**Rationale:** These features depend on the deployed, hardened, persistent relay from Phases 1–3. The drop box requires lifespan infrastructure from Phase 3. File TTL requires the drop box to exist. Connection status requires the `GET /m/{code}/status` endpoint which builds on the mount registry.
**Delivers:** Production-ready UX — social sharing previews, clear agent-offline indicators, public anonymous file drop with auto-cleanup.
**Features addressed:** Relay landing page + OG tags, connection status expanded states (503/410), default always-on drop box, per-file upload TTL.
**Avoids:** Pitfall 2 (drop box startup race — health check must gate on drop box registration), Pitfall 4 (file deletion mid-download — reference counting), Pitfall 9 (asyncio task GC — strong task references), Pitfall 8 (reserved code hijack — `RESERVED_CODES` frozenset), Pitfall 10 (UI shows "Connected" while agent is offline — poll `/m/{code}/status`).
**Research flag:** Pitfall-heavy phase. The drop box embedded agent lifecycle (in-process vs subprocess), TTL cleanup loop design (per-file tasks vs single periodic sweep), and connection status polling interval all benefit from a research-phase pass before implementation.

### Phase Ordering Rationale

- **Security before features:** CORS, cookies, and proxy headers are blocking security bugs that only manifest in production. They must land in Phase 1 with the Dockerfile, not retrofitted later.
- **Harden before persist:** Rate limiting in Phase 2 protects the public relay before adding the complexity of SQLite persistence in Phase 3. The rate limiter also exercises the lifespan pattern at smaller scope before the full persistence layer.
- **Persist before polish:** The drop box (Phase 4) requires a working lifespan handler with registered services (Phase 3). The TTL file cleanup must coordinate with the drop box mount. The connection status endpoint queries the registry.
- **Dockerfile CI loop:** Building and testing the Docker image locally after Phase 1 (before Phases 2–4) validates the container environment early and avoids discovering routing bugs (Vite assets caught by mount proxy) after significant additional work.

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (SQLite Persistence):** GCS FUSE vs `/tmp` + `--min-instances=1` storage strategy needs a concrete decision based on acceptable data loss semantics and Cloud Run billing constraints. The WAL vs DELETE journal mode choice is critical and deployment-environment-specific.
- **Phase 4 (UX Polish):** Three sub-features have non-trivial lifecycle interactions — embedded drop box agent startup ordering, asyncio TTL task reference management, and the reserved code protection mechanism. A research-phase pass is recommended before planning implementation steps.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 1 (Cloud Run Foundation):** FastAPI + uv Docker deployment is officially documented and widely deployed. Proxy header configuration, CORS lockdown, and structured logging are all solved problems with official docs.
- **Phase 2 (Abuse Prevention):** slowapi integration with FastAPI is well-documented in the library's own README. The `--max-instances=1` single-instance constraint simplifies the implementation to standard decorator usage.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 4 new dependencies verified on PyPI with specific versions. Alternatives evaluated and ruled out with concrete reasons. Official FastAPI docs recommend pydantic-settings. |
| Features | HIGH | Feature set derived from codebase analysis of existing v1.2 code + official Cloud Run docs + verified community patterns for tunnel services. Complexity estimates grounded in specific file counts and existing patterns to reuse. |
| Architecture | HIGH | Component-level analysis performed against the actual codebase (`relay/app/`, `server/app/`, `client/src/`). Build order is dependency-driven with explicit test points per step. Data flow changes are fully traced. |
| Pitfalls | HIGH | Critical pitfalls (SQLite WAL on FUSE, proxy headers, CORS credentials) verified against official docs, SQLite FAQ, FastAPI CORS documentation, and GCP documentation. asyncio Task GC pitfall is documented in Python stdlib docs. |

**Overall confidence:** HIGH

### Gaps to Address

- **GCS FUSE vs `/tmp` SQLite decision:** Research confirms GCS FUSE works with `journal_mode=DELETE` for low-frequency writes, but the practical tradeoff (losing mount codes on redeploy vs $5–10/month for `--min-instances=1`) is a product decision, not a technical one. Needs an explicit decision before Phase 3 implementation starts.
- **Drop box embedded agent implementation path:** Two options exist — in-process (`run_agent_loop()` via `asyncio.create_task`) vs subprocess (`asyncio.create_subprocess_exec`). The in-process path avoids process management but shares the event loop. The subprocess path isolates failures but requires IPC. Research is inconclusive on which is more robust for Cloud Run's SIGTERM handling.
- **Vite SPA serving vs mount proxy route conflict (Pitfall 7):** Assets served at wrong path or caught by mount proxy catch-all. Fix is known (mount `/assets` StaticFiles before the mount proxy router) but specific asset paths depend on current Vite build output. Needs a local `docker run` test immediately after Phase 1 Dockerfile is written.
- **Cloud Run session affinity for WebSocket connections:** `--session-affinity` behavior with WebSocket upgrade requests needs validation in staging. The tunnel protocol relies on browser and agent hitting the same instance; session affinity must be verified to work for WebSocket connections, not just HTTP.

## Sources

### Primary (HIGH confidence)
- [Cloud Run health check configuration](https://docs.cloud.google.com/run/docs/configuring/healthchecks) — startup probe, liveness probe, 200 response requirement
- [Cloud Run Cloud Storage volume mounts](https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts) — GCS FUSE limitations, no POSIX locking
- [Cloud Run min-instances](https://docs.cloud.google.com/run/docs/configuring/min-instances) — scale-to-zero behavior, warm instance for WebSocket services
- [Cloud Run PORT env var](https://cloud.google.com/run/docs/configuring/services/environment-variables) — injected `$PORT`, must not hardcode
- [Cloud Run structured logging](https://cloud.google.com/run/docs/logging) — `severity` field, JSON format requirements
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) — wildcard + credentials incompatibility
- [FastAPI settings docs](https://fastapi.tiangolo.com/advanced/settings/) — official pydantic-settings recommendation
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/) — lifespan context manager pattern
- [slowapi GitHub](https://github.com/laurentS/slowapi) — per-process counter limitation, Cloud Run caveat
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) — v0.22.1, Python 3.11+ compatibility
- [structlog docs](https://www.structlog.org/) — v25.5.0, JSONRenderer for production
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) — v2.13.1
- [SQLite WAL documentation](https://sqlite.org/wal.html) — shared memory requirement, network filesystem prohibition
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker/) — multi-stage Dockerfile patterns, layer caching
- [asyncio Task GC (Python docs)](https://docs.python.org/3/library/asyncio-task.html) — "Task was destroyed but it is pending" warning
- Codebase analysis: `relay/app/`, `server/app/`, `client/src/`, `agent/`, `pyproject.toml`

### Secondary (MEDIUM confidence)
- [SQLite on Cloud Run with GCS FUSE](https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun/) — practical WAL mode + FUSE tradeoff with real-world validation
- [Cloud Run FastAPI quickstart](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service) — updated 2026-03-12, Dockerfile patterns
- [FastAPI CORS production 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026) — CORS lockdown with `allow_credentials=True`
- [Open Graph meta tag testing](https://dev.to/shadowfaxrodeo/i-tested-every-link-preview-meta-tag-on-every-social-media-and-messaging-app-so-you-dont-have-to-it-was-super-boring-39c0) — OG tag behavior across platforms

### Tertiary (LOW confidence)
- [GCS FUSE locking limitation discussion](https://discuss.google.dev/t/connecting-cloud-run-to-a-persistent-storage-solution/124337) — confirmed locking limitation via community post, not official GCP statement
- [APScheduler versions](https://pypi.org/project/APScheduler/) — v4.0a6 confirmed pre-release/alpha; inference that asyncio.create_task is simpler for one-shot TTL tasks

---
*Research completed: 2026-03-16*
*Ready for roadmap: yes*
