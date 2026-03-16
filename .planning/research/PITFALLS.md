# Domain Pitfalls

**Domain:** Adding Cloud Run deployment, SQLite persistence, rate limiting, CORS lockdown, file TTL, and always-on mounts to existing FastAPI relay/tunnel file sharing system (v1.3)
**Researched:** 2026-03-16
**Confidence:** HIGH (codebase analysis of relay/agent infrastructure + verified external patterns from official docs and community post-mortems)

---

## Critical Pitfalls

### Pitfall 1: SQLite WAL Mode Silently Corrupts on Cloud Storage FUSE Mounts

**What goes wrong:**
Cloud Run's container filesystem is ephemeral. The natural fix is to mount a Cloud Storage bucket via GCS FUSE as a persistent volume. Developers enable SQLite WAL mode expecting better concurrent write performance. The mount registry DB works fine during development with a local file, then starts corrupting under concurrent writes on Cloud Run.

WAL mode requires that all reader processes share a `-shm` (shared memory) file alongside the `.db` file. Cloud Storage FUSE does not provide POSIX byte-range locking — it uses an optimistic object-store model where concurrent writes can overwrite each other. WAL's journal cannot safely operate over FUSE because the shared memory file is process-local and cannot be coordinated across restarts or concurrent instances.

**Why it happens:**
The developer knows WAL mode is "better" and enables it without checking whether the underlying filesystem guarantees POSIX locking semantics. Local development on macOS/Linux passes because the host filesystem satisfies all constraints. Production on Cloud Run FUSE fails silently: writes appear to succeed but the WAL log is never properly checkpointed, leaving the DB in an inconsistent state after a restart.

**Consequences:**
- Database corruption that only surfaces after a Cloud Run instance restarts (e.g., scale-to-zero then cold start)
- Mount registry entries appear to persist but are unreadable
- SQLite `SQLITE_IOERR` or `SQLITE_CORRUPT` errors on the first access after restart
- WAL checkpoint hangs indefinitely, starving all writers

**Prevention:**
- Use **Cloud Filestore** (managed NFS with POSIX locking semantics) if budget allows, or accept ephemeral in-memory state and use `--min-instances=1` to keep the container alive
- If GCS FUSE is used, disable WAL mode entirely: `PRAGMA journal_mode=DELETE` and `PRAGMA synchronous=FULL`. Accept the write serialization cost — the mount registry has low write frequency.
- Set `busy_timeout` (e.g., `PRAGMA busy_timeout=5000`) to handle the serialized write contention gracefully
- Never open the SQLite DB file over a network path. The SQLite FAQ explicitly states: "Do not use WAL mode on a network filesystem"
- For v1.3 scale (single-digit concurrent users), the simpler and safer approach is `--min-instances=1` with an in-process SQLite file on local container storage, accepting data loss on redeploy. Use Google Cloud SQL for true persistence.

**Detection:**
- `SQLITE_BUSY` errors in logs on first request after cold start
- Database file has a `-wal` or `-shm` sibling file on GCS FUSE (a sign WAL mode is active where it shouldn't be)
- Mount registry empty after every Cloud Run redeploy

**Phase to address:** SQLite persistent mount registry phase. The storage backend decision must be made before any schema design.

---

### Pitfall 2: Cloud Run Scale-to-Zero Silently Kills the Always-On Drop Box Mount

**What goes wrong:**
The always-on public drop box is implemented as an internal agent that starts with the relay container and registers a well-known mount code on startup. When Cloud Run scales to zero (no traffic for a period), the container is terminated. When a new request arrives and a new instance starts, the drop box agent starts fresh — but its agent WebSocket connection and registration are part of the same process startup. If startup ordering is wrong (e.g., the relay app starts accepting traffic before the internal agent has connected and registered), the first user gets a 503 or 404 for the drop box.

**Why it happens:**
Cloud Run starts a container and routes traffic as soon as the `/health` endpoint responds 200. If the internal agent uses `asyncio.create_task()` to register in the background (fire-and-forget), requests can arrive before registration completes. On a cold start, the gap between HTTP health-check passing and agent registration can be 500ms–2s, easily long enough for the first user request to fail.

**Consequences:**
- First request to the drop box after a cold start returns 404 or 503
- Users report "broken" drop box link even though the service is "healthy"
- Retrying works, confusing users and making the bug hard to reproduce

**Prevention:**
- Start the internal drop box agent inside a FastAPI `lifespan` context manager (not a fire-and-forget task), and `await` registration confirmation before the app is ready to serve traffic. Cloud Run will continue routing the startup request until the lifespan completes.
- Set `--min-instances=1` on the Cloud Run service to prevent scale-to-zero entirely. This eliminates the cold start race at the cost of ~$5–10/month in minimum billing.
- Implement a health check endpoint that returns 200 only after the drop box agent is registered, not just after uvicorn starts listening.

**Detection:**
- First-request 404 or 503 that disappears on retry
- Logs show agent registration completing 1–3 seconds after first inbound request
- Health check passes but `/m/{drop-box-code}/` returns error

**Phase to address:** Default always-on public drop box mount phase (and Cloud Run deployment phase for the health check design).

---

### Pitfall 3: CORS Wildcard Cannot Be Used With Credentials — Breaks Cookie Auth

**What goes wrong:**
The existing relay (`relay/app/main.py:22`) sets `allow_origins=["*"]`. The app uses itsdangerous cookie-based sessions for per-mount password auth. When the CORS wildcard is replaced with explicit origins as part of "CORS lockdown," the developer adds `allow_credentials=True` to stop session cookies from being stripped on cross-origin requests. This silently breaks: browsers reject `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true` as invalid (RFC 6454 and the Fetch spec both prohibit this).

**Why it happens:**
The developer adds `allow_credentials=True` to enable cookie forwarding, not realizing that this setting is incompatible with wildcard origins. The browser enforces the incompatibility silently — the request succeeds but the session cookie is stripped, so every API call looks like an unauthenticated request.

**Consequences:**
- Password-protected mounts always redirect to login even after successful auth
- Session cookies set on login are never sent on subsequent requests
- The bug manifests only when the React SPA is served from a different origin than the relay (e.g., during local dev at `localhost:5173` hitting relay at `localhost:8000`)

**Prevention:**
- When using cookie-based auth, `allow_origins` must be an explicit list (never `"*"`). Use environment variable `RELAY_ALLOWED_ORIGINS` and parse it at startup.
- The rule: if `allow_credentials=True`, then `allow_origins` must be an explicit list. If `allow_origins=["*"]`, then `allow_credentials` must be `False` (or omitted).
- For Cloud Run, the relay serves the React SPA directly, so all requests are same-origin and CORS is irrelevant for browser-to-relay calls. CORS is only needed for the agent's WebSocket registration endpoint (which doesn't use cookies). These two concerns should be scoped separately.
- Document the origin list in config. Never hardcode origins; use an environment variable.

**Detection:**
- Session cookies present in login response headers but absent in subsequent API request headers
- 401 or redirect-to-login on every protected request despite successful login
- Browser DevTools shows `Access-Control-Allow-Credentials: true` alongside `Access-Control-Allow-Origin: *` (this should never appear; one or the other browser will error)

**Phase to address:** CORS lockdown phase. Must be addressed before any authentication testing of the production deployment.

---

### Pitfall 4: Per-File TTL Deletion Race — File Deleted While Download Is In Progress

**What goes wrong:**
A file has a TTL of 10 minutes. A user starts downloading a 500MB file at minute 9:58. At minute 10:00, the background TTL cleanup task calls `os.remove()` on the file. On Linux (and inside Docker), `os.remove()` unlinks the file from the directory while the open file descriptor held by the download stream is still valid — the download finishes successfully. However, if the cleanup closes the aiofiles handle first, or if the download is through the relay tunnel (where the agent holds the file handle), closing the handle causes the download to fail mid-stream with an unexpected EOF.

The more dangerous variant: the upload endpoint uses `aiofiles` to write a file and registers a TTL cleanup task. The TTL fires during a slow upload (not download), truncating the partial file and leaving an orphaned inode.

**Why it happens:**
TTL cleanup is implemented as an `asyncio.create_task()` that fires at a scheduled time, without awareness of whether any in-progress operation holds a reference to the file. On Cloud Run restarts, all pending tasks are destroyed without cleanup — any files uploaded in the last TTL window are never deleted.

**Consequences:**
- In-progress downloads fail mid-stream with EOF
- Uploads create partial files that are never cleaned up on container restart
- Disk fills up with orphaned partial uploads (especially dangerous on the drop box)
- Users see "connection lost" errors near the end of large downloads

**Prevention:**
- Track active file handles in a per-file reference counter. The TTL cleanup checks: if `ref_count > 0`, defer deletion by 30 seconds and reschedule. Only delete when `ref_count == 0`.
- On Cloud Run container shutdown (`SIGTERM`), run a cleanup pass that deletes all files past their TTL before the process exits. Register a `lifespan` shutdown handler for this.
- Use a single, dedicated cleanup task (not one task per file) that wakes on a fixed interval (e.g., every 60 seconds), scans all files, and deletes those past TTL with `ref_count == 0`. This is more robust than per-file scheduled tasks that disappear on restart.
- Store file TTL metadata in SQLite (or in a separate JSON sidecar) so that a new container instance after restart can re-enqueue cleanup for files uploaded before the restart.

**Detection:**
- Downloads failing in final 10% with unexplained EOF
- Disk usage growing monotonically over time (orphaned files)
- Partial files (zero bytes or incomplete) accumulating in the drop box directory

**Phase to address:** Per-file upload TTL with auto-deletion phase.

---

### Pitfall 5: Rate Limiter Counter Is Per-Process, Not Per-Relay-Instance

**What goes wrong:**
slowapi (the standard FastAPI rate limiter) uses an in-memory counter by default, scoped to the current Python process. On Cloud Run, each instance is a separate container. An attacker making 100 requests per second spreads them across 5 Cloud Run instances (Cloud Run autoscales), so each instance sees 20 req/s — below the per-process limit of 30 req/s — and none of them trigger rate limiting. The attacker effectively has an unlimited rate limit.

**Why it happens:**
The developer tests rate limiting locally with a single process and it works. On Cloud Run with multiple instances, the in-memory counter is split across instances. Even `--min-instances=1` doesn't help if Cloud Run scales out under load.

**Consequences:**
- Brute-force attacks on mount codes succeed despite rate limiting being "enabled"
- Mount registration floods exhaust server memory on individual instances
- Attack traffic that would be blocked by a single-instance rate limiter passes through at scale

**Prevention:**
- For v1.3 (small scale, friend tier, `--min-instances=1`), in-process rate limiting with slowapi is acceptable as a first line of defense, but document the limitation explicitly.
- The correct production solution: use a shared counter store (Redis, Memorystore) with `fastapi-limiter` (which uses Redis natively). For v1.3 this may be over-engineered; accept the limitation.
- For mount code lookups specifically (the high-risk endpoint), implement rate limiting in the application layer even without Redis: track failed lookup counts in the SQLite registry with a `last_failure_ts` and `failure_count` column, reset per TTL window. SQLite writes are serialized — this is correct-by-construction for counting.
- WebSocket connections (agent registration) are long-lived, not per-request. Rate limit by counting active connections per source IP at the `agent_ws.py` level using a module-level `dict[str, int]` counter, not via slowapi middleware.

**Detection:**
- Failed mount code attempts per IP exceed the intended limit when tested from multiple IPs
- CloudRun metrics show autoscaling to 2+ instances during a brute-force test
- Rate limit 429 responses never appear in logs despite high invalid-code request rate

**Phase to address:** Rate limiting and abuse prevention phase. Accept in-process limitation for v1.3 with explicit documentation.

---

## Moderate Pitfalls

### Pitfall 6: uvicorn Behind Cloud Run's HTTPS Proxy Does Not See Secure Requests

**What goes wrong:**
Cloud Run terminates TLS at its load balancer and forwards plain HTTP to uvicorn inside the container. The `request.url.scheme` inside FastAPI is `http`, not `https`. The itsdangerous session cookie is set with `secure=True`, which means the browser only sends it over HTTPS. The app sets `secure=True` based on `request.url.scheme == "https"`, which is always `False` inside the container. Session cookies are set with `secure=False`, meaning they're transmitted insecurely in any future context, and the `SameSite=None; Secure` requirement for cross-site cookies is never satisfied.

**Why it happens:**
The container doesn't know it's behind a TLS proxy unless uvicorn is told to trust `X-Forwarded-Proto`. The default uvicorn configuration does not forward proxy headers.

**Prevention:**
- Add `--proxy-headers` to the uvicorn start command. This enables uvicorn to read `X-Forwarded-Proto: https` and `X-Forwarded-For` headers from Cloud Run's proxy and set `request.url.scheme` correctly.
- Also add `--forwarded-allow-ips=*` (or the specific Cloud Run IP range) to prevent header spoofing by untrusted callers. On Cloud Run, all traffic arrives through the load balancer so `*` is acceptable.
- In the Dockerfile CMD, use: `uvicorn relay.app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
- Validate: after deployment, `request.url.scheme` must equal `https` in production handlers.

**Detection:**
- Session cookies appear with `Secure` flag unset in browser DevTools despite HTTPS URL
- `request.url.scheme` logs `http` in production Cloud Run handlers
- Clipboard sync and other features requiring `navigator.clipboard` (HTTPS-only browser API) fail on the relay-served UI

**Phase to address:** Cloud Run Dockerization phase (very first deployment task).

---

### Pitfall 7: Vite Base Path Not Set, React SPA Loads White Screen on Cloud Run

**What goes wrong:**
The React SPA is built with Vite. In the Dockerfile, the frontend is built with `npm run build` and the resulting `dist/` directory is served by FastAPI as static files. On Cloud Run, all URLs go through Cloud Run's HTTPS proxy, and the app is at `https://relay.example.com/`. The SPA loads a blank white screen. The browser console shows `Failed to load resource: net::ERR_ABORTED 404` for `/assets/index-XXXX.js`.

The asset paths in `dist/index.html` are `/assets/index-XXXX.js` (absolute paths). FastAPI's `StaticFiles` serves them at `/assets/index-XXXX.js`, which conflicts with the mount proxy catch-all route `/m/{code}/{path:path}`. Route registration order matters — if `StaticFiles` is mounted before the mount proxy, it works. If after, the mount proxy steals `/assets/` paths before StaticFiles sees them.

**Why it happens:**
FastAPI route/mount order determines precedence. `app.mount("/assets", StaticFiles(...))` must appear before `app.include_router(mount_proxy_router)`, or the path `/assets/...` matches the mount proxy's `/{code}/{path:path}` pattern first (since `assets` looks like a mount code).

**Prevention:**
- Mount `/assets` and `/` (index.html fallback) before including the mount proxy router.
- Use Vite's `base: "./"` setting only if serving from a sub-path; for root deployment, the default (`/`) is correct.
- In the multi-stage Dockerfile, set `VITE_BASE_URL=/` explicitly to avoid relative-path issues.
- Integration test: build the Docker image locally and verify `curl http://localhost:8080/assets/index-XXXX.js` returns 200 before deploying to Cloud Run.

**Detection:**
- Blank white page on relay root URL after Docker deployment
- Browser console shows 404 for `/assets/index-XXXX.js`
- Direct `curl` to asset URL returns HTML (the mount proxy error page) instead of JavaScript

**Phase to address:** Cloud Run Dockerization phase. Test locally with `docker run -p 8080:8080` before pushing to Cloud Run.

---

### Pitfall 8: The Default Drop Box Shares a Mount Registry With User Mounts — Code Collision Risk

**What goes wrong:**
The default drop box uses a well-known, fixed mount code (e.g., `dropbox`). The mount registry allows agents to request a specific code via the `code` query parameter. Nothing in `agent_ws.py` (current code) prevents a user from registering an agent with code `dropbox`, overwriting the internal drop box registration. The current `agent_ws.py` logic is: "if the code is not occupied, assign it; otherwise generate a new one." A user agent connecting with `?code=dropbox` when the drop box is momentarily offline (e.g., during startup) gets assigned `dropbox`, hijacking the well-known code.

**Why it happens:**
The code reservation and "taken" check in `agent_ws.py` (line 36–39) is designed for reconnect semantics (reclaim your old code), not for protecting reserved codes. There is no concept of a "reserved" or "system" code.

**Prevention:**
- Maintain a set of reserved codes in the relay config: `RESERVED_CODES = frozenset({"dropbox"})`. External agents attempting to register a reserved code should be rejected with WebSocket close code `4009` (Policy Violation).
- The internal drop box agent should connect with a privileged startup path that bypasses the "occupied" check and is always allowed to reclaim its reserved code.
- Alternatively, use a private registration endpoint (different from `/agent/ws`) for internal agents only, not accessible to external callers.

**Detection:**
- Drop box URL returns a user's personal mount instead of the shared drop box
- Agent logs show successful registration with code `dropbox` from an unexpected IP
- Internal drop box agent fails to register because code is already occupied

**Phase to address:** Default always-on public drop box mount phase.

---

### Pitfall 9: asyncio.create_task for TTL Cleanup Is Silently Dropped Under Certain Conditions

**What goes wrong:**
Per-file TTL cleanup is implemented as `asyncio.create_task(delete_after(path, delay_s))`. In Python 3.11+, if the Task object is not referenced anywhere after creation (fire-and-forget), the garbage collector may destroy the Task before it fires — Python emits a "Task was destroyed but it is pending" warning and the cleanup never runs. On Cloud Run restart (SIGTERM), all pending tasks are cancelled immediately without running their cleanup logic.

**Why it happens:**
`asyncio.create_task()` returns a Task but fire-and-forget usage discards the reference. The asyncio event loop holds a weak reference to running tasks, not a strong one. Under memory pressure or GC cycles, the task disappears.

**Consequences:**
- Files accumulate on disk, never deleted
- The drop box disk fills up over time with uploaded files past TTL
- No error visible — the cleanup just silently stops running

**Prevention:**
- Store all pending cleanup Tasks in a module-level `set` and add a `done_callback` that removes the task from the set when it completes. This keeps a strong reference until completion: `_cleanup_tasks: set[asyncio.Task] = set(); t = asyncio.create_task(...); _cleanup_tasks.add(t); t.add_done_callback(_cleanup_tasks.discard)`.
- On SIGTERM (Cloud Run shutdown), cancel all pending cleanup tasks and run a synchronous cleanup sweep as part of the lifespan shutdown handler.
- Prefer a single periodic cleanup loop over per-file tasks: on each tick, scan all tracked files, delete those past their TTL. Fewer tasks, simpler lifecycle.

**Detection:**
- "Task was destroyed but it is pending" warning in uvicorn logs
- Files with creation timestamps past their TTL still present on disk after hours
- Drop box disk usage growing monotonically with no cleanup events in logs

**Phase to address:** Per-file upload TTL with auto-deletion phase.

---

### Pitfall 10: WebSocket Connection Status UI Desynchronizes From Actual Agent State

**What goes wrong:**
The UI shows "Connected" because the browser WebSocket to the relay is alive. But the relay's TunnelConnection to the agent is offline (agent laptop slept, went behind a NAT, etc.). The relay's tunnel heartbeat detects the offline agent and marks the mount `OFFLINE` in the registry. The browser WebSocket to the relay is still connected — the browser doesn't know the agent is gone until it makes a proxied API call that returns 503.

The inverse also occurs: the browser WebSocket drops (mobile WiFi handoff), but the React code only updates the status to "Disconnected" after a WebSocket `close` event. If the TCP connection is silently dropped (no FIN/RST), the browser WebSocket may stay in `OPEN` state for 30–90 seconds before the ping/pong timeout fires.

**Why it happens:**
There are two independent connection states that the UI must track: the browser-to-relay WebSocket AND the relay-to-agent tunnel. Most implementations only track the former. The UI infers agent health from "can I connect to the relay?" but the relay can be reachable while the agent is offline.

**Prevention:**
- Add a relay-side API endpoint `GET /m/{code}/status` that returns the current `MountStatus` (ONLINE/OFFLINE/EXPIRED). The UI polls this endpoint every 10 seconds or listens for a status push over the browser WebSocket.
- Alternatively, inject mount status into WebSocket keepalive frames: when the relay sends a heartbeat ping to the browser WebSocket, include the current agent connection state as a JSON payload. The UI updates its status badge accordingly.
- Use WebSocket `readyState` (`CONNECTING=0, OPEN=1, CLOSING=2, CLOSED=3`) for the browser-to-relay connection state, and the above mechanism for the relay-to-agent state. The UI should show "Relay connected, agent offline" as a distinct state from "Relay disconnected."

**Detection:**
- UI shows "Connected" while all API calls return 503
- Status badge stays green for 60+ seconds after agent disconnects
- Users report "everything looks fine but nothing works"

**Phase to address:** Connection status indicator in web UI phase.

---

## Minor Pitfalls

### Pitfall 11: Structured Logging Format Conflicts With Cloud Run's JSON Log Parser

**What goes wrong:**
Cloud Run expects JSON-formatted logs where the severity field is named `severity` (not `level`). Python's `logging` module by default emits plaintext. If logs are emitted as `{"level": "INFO", "message": "..."}` (a common Python structured logging format), Cloud Run's log viewer shows the entire JSON blob as a single string at severity INFO — no severity-based filtering, no log correlation by `trace` ID.

**Prevention:**
- Use `python-json-logger` with the Cloud Run-specific field mapping: `severity` (not `level`), `message` (standard), `time` (RFC 3339 format). See the [Cloud Run structured logging documentation](https://cloud.google.com/run/docs/logging#writing-structured-logs).
- Set `LOG_FORMAT=json` via environment variable, falling back to human-readable plaintext for local development.

**Phase to address:** Cloud Run Dockerization phase.

---

### Pitfall 12: `Dockerfile` Uses uv But Does Not Cache the Lock File Correctly

**What goes wrong:**
The `Dockerfile` runs `uv sync` to install dependencies. If the `COPY` instruction copies the entire project directory before running `uv sync`, every code change invalidates the Docker layer cache for the dependency install step. A 30-second dependency install runs on every `docker build`, even when `uv.lock` hasn't changed.

**Prevention:**
- Copy only `pyproject.toml` and `uv.lock` first, run `uv sync --frozen --no-install-project`, then copy the rest of the source. This caches the installed virtualenv layer and only invalidates it when the lock file changes.
- Use `uv sync --frozen` (not `uv install`) to ensure the exact versions from `uv.lock` are installed without resolution.

**Phase to address:** Cloud Run Dockerization phase.

---

### Pitfall 13: Mount Code in `X-Mount-Code` Response Header Leaks to Relay-Served Pages

**What goes wrong:**
The mount proxy currently rewrites HTML to prefix asset paths with `/m/{code}`. If the relay ever adds the mount code to response headers (e.g., for debugging, `X-Mount-Code: abc123`), those headers are forwarded to the browser. The mount code appears in browser DevTools and server-side access logs of any CDN or proxy sitting in front of Cloud Run, undermining the secrecy of short-lived codes.

**Prevention:**
- The relay should never add mount code identifiers to outbound response headers.
- Review all headers added by middleware and ensure none leak the mount code outside the URL path.

**Phase to address:** Cloud Run hardening / security review.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| Cloud Run Dockerization | uvicorn not getting `--proxy-headers`; cookies show `Secure=False` in HTTPS context | Add `--proxy-headers --forwarded-allow-ips='*'` to CMD |
| Cloud Run Dockerization | Docker layer cache invalidated on every build | Copy `pyproject.toml` + `uv.lock` before source files; use `uv sync --frozen` |
| Cloud Run Dockerization | React SPA assets return 404 or hit mount proxy catch-all | Mount `/assets` before including mount proxy router; test with `docker run` locally |
| Cloud Run Dockerization | Container ready before drop box agent registered | Use `lifespan` context manager; health check verifies drop box registration |
| SQLite persistent mount registry | WAL mode corruption on GCS FUSE | Use `journal_mode=DELETE` + `synchronous=FULL` on FUSE; prefer Filestore or `--min-instances=1` |
| SQLite persistent mount registry | DB not reopened correctly after cold start | Test full cold-start cycle: deploy, wait for scale-to-zero, send request, verify registry state |
| Rate limiting | In-process counters split across Cloud Run instances | Use SQLite-backed failure counters for mount lookups; document multi-instance limitation |
| Rate limiting | WebSocket connections not rate-limited by slowapi | Rate-limit agent connections in `agent_ws.py` using module-level IP counter |
| CORS lockdown | `allow_credentials=True` with `allow_origins=["*"]` breaks cookies | Explicit origin list when credentials are used; never combine wildcard with credentials |
| CORS lockdown | Relay serves SPA so most calls are same-origin; CORS only needed for agent WS | Scope CORSMiddleware to `/agent/ws` only, not globally |
| Connection status UI | Browser WebSocket alive but agent tunnel dead; UI shows "Connected" | Poll `GET /m/{code}/status` or push agent state via browser WebSocket heartbeat |
| Connection status UI | Stale "Connected" state during browser network handoff | Implement explicit ping/pong with 15-second timeout; update UI on pong timeout |
| File TTL auto-deletion | Fire-and-forget `asyncio.create_task` silently dropped | Store task references in a module-level set; prefer single periodic cleanup loop |
| File TTL auto-deletion | Cleanup tasks lost on Cloud Run SIGTERM | Register SIGTERM handler to run cleanup sweep before exit |
| File TTL auto-deletion | File deleted mid-download causing EOF | Track open file handle reference counts before deleting |
| Always-on drop box | Reserved code hijacked by user agent on startup race | Validate incoming `code` against RESERVED_CODES; reject with WS close 4009 |
| Always-on drop box | Scale-to-zero destroys drop box; first request after cold start fails | Set `--min-instances=1`; health check waits for drop box registration |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Cloud Run + uvicorn proxy headers | `request.url.scheme == "http"` inside container; cookies get `Secure=False` | Start uvicorn with `--proxy-headers --forwarded-allow-ips='*'` |
| Cloud Run + SQLite WAL | WAL mode on GCS FUSE volume causes DB corruption | Use `journal_mode=DELETE` on FUSE; use `--min-instances=1` to avoid scale-to-zero |
| Cloud Run + always-on drop box | Drop box unregistered between container startup and first traffic | Use `lifespan` to await registration; health check gates on drop box being registered |
| CORSMiddleware + cookie auth | Wildcard origins + `allow_credentials=True` silently breaks session cookies | Explicit origin list when credentials enabled; validate with browser DevTools cookie inspector |
| Rate limiter (slowapi) + Cloud Run autoscaling | Per-process counters split across instances; brute force succeeds at scale | SQLite-backed failed-attempt counters for high-value endpoints |
| File TTL + asyncio | `create_task` fire-and-forget: task GC'd before firing | Strong reference in module-level set; periodic cleanup loop preferred over per-file tasks |
| File TTL + Cloud Run SIGTERM | Container killed without running cleanup; files orphaned | lifespan shutdown handler runs cleanup sweep |
| Connection status UI + dual connection model | UI tracks browser-to-relay WS only; agent going offline is invisible | Add relay-side `GET /m/{code}/status` endpoint; push status in WS heartbeat payloads |
| Default drop box + reserved codes | User agent can claim drop box code during startup gap | Reserved code set in config; agent_ws.py checks against reserved codes on registration |
| Multi-stage Docker + Vite | Assets served at wrong path or caught by mount proxy router | Mount `/assets` StaticFiles before mount proxy router; test locally with `docker run` |

---

## Security Mistakes for v1.3

| Mistake | Risk | Prevention |
|---------|------|------------|
| uvicorn without `--proxy-headers` | `request.url.scheme == "http"` causes `Secure=False` cookies sent over any protocol | Add `--proxy-headers` to uvicorn CMD in Dockerfile |
| `allow_origins=["*"]` + cookie auth in production | Session cookies stripped by browser; all authenticated sessions fail | Explicit `allow_origins` list from environment variable |
| No reserved code enforcement | User agent can claim well-known drop box code | Check incoming code against `RESERVED_CODES` frozenset before registration |
| SQLite WAL on GCS FUSE | DB corruption after restart | Disable WAL on non-local filesystems; use `PRAGMA journal_mode=DELETE` |
| Rate limiting per-process only | Brute force mount codes across Cloud Run instances | Accept limitation for v1.3; document; use SQLite-backed counters for critical endpoints |
| File cleanup task GC | Orphaned files accumulate; disk fills; drop box degrades | Strong task references; periodic cleanup loop; SIGTERM cleanup sweep |

---

## Sources

- Direct codebase analysis: `relay/app/main.py` (`allow_origins=["*"]`, no CORS scoping), `relay/app/routers/agent_ws.py` (code reservation logic, no reserved code check), `relay/app/services/mount_registry.py` (in-memory only, no persistence), `relay/app/routers/mount_proxy.py` (proxy architecture)
- [SQLite WAL mode documentation](https://sqlite.org/wal.html) — WAL requires shared memory; does not work over network filesystems
- [SQLite on networked storage - GoToSocial documentation](https://docs.gotosocial.org/en/latest/advanced/sqlite-networked-storage/) — FUSE/NFS incompatibility with SQLite locking, corruption risk
- [Cloud Run WebSocket documentation](https://docs.cloud.google.com/run/docs/triggering/websockets) — 5-minute default timeout; up to 60 minutes configurable; subject to request timeout
- [Cloud Run minimum instances documentation](https://docs.cloud.google.com/run/docs/configuring/min-instances) — scale-to-zero behavior; how to keep instances warm
- [How to Deploy SQLite on Cloud Run](https://www.wallacesharpedavidson.nz/post/sqlite-cloudrun/) — persistent volume options, FUSE limitations
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/) — wildcard + credentials incompatibility
- [FastAPI CORSMiddleware + credentials restriction (GitHub #830)](https://github.com/TracecatHQ/tracecat/pull/830) — wildcard origins incompatible with `allow_credentials=True`
- [slowapi GitHub](https://github.com/laurentS/slowapi) — per-process counter limitation; Redis backend for distributed rate limiting
- [Cloud Run structured logging documentation](https://cloud.google.com/run/docs/logging) — `severity` field name; JSON format requirements
- [FastAPI deployment with Docker](https://fastapi.tiangolo.com/deployment/docker/) — multi-stage build patterns, layer caching
- [asyncio Task GC warning (Python docs)](https://docs.python.org/3/library/asyncio-task.html) — "Task was destroyed but it is pending" — fire-and-forget task pitfall
- [WebSocket readyState MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket/readyState) — connection states; does not reflect tunnel-to-agent health
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html) — connection exhaustion, rate limiting best practices

---
*Pitfalls research for: Network File Server v1.3 — productionize friend tier*
*Researched: 2026-03-16*
