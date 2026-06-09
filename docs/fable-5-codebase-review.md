# Codebase Review — Claude Fable 5 (2026-06-09)

Full-codebase analysis performed by Claude Code (model: claude-fable-5), covering all six
Python packages (`server`, `relay`, `agent`, `tunnel`, `accounts`, `shared`), the React/TS
`client`, and the test/build/ops infrastructure. Companion to `modularity-audit.md`
(several of that audit's recommendations have since been implemented; this review notes
what remains and adds new findings).

---

## 1. Functionality & Reusability

**In one sentence:** a self-hosted "ngrok + Google Drive lite" — share a local folder over
LAN with a web UI, and optionally tunnel it through a public relay with full user
accounts, groups, and access control.

| Component | What it does | Reusability |
|---|---|---|
| `tunnel/` | Custom binary stream-multiplexing protocol over a single WebSocket (HTTP/2-lite: OPEN/DATA/CLOSE/CANCEL frames + WS bridging + heartbeat + per-stream backpressure) | **10/10 — drop-in.** Zero project imports, framework-decoupled via `typing.Protocol`, clean `__all__` |
| `accounts/` | Users, groups (nested, cycle-safe), bcrypt passwords, quotas; abstract `AccountStore` + SQLite impl | **10/10 — drop-in.** Framework-agnostic, typed exceptions, frozen dataclass models |
| `shared/` | `compute_backoff`, `parse_duration`, `repo_root` | **9/10** (`paths.py` assumes this repo's layout) |
| `server/` | FastAPI app: file CRUD, streaming ZIP, search, previews with Range support, share links, clipboard sync, file requests, WebSocket device presence | **7/10** — services are mutually independent, but glued by ~9 module-level singletons; `files.py` reverse-imports the relay |
| `relay/` | Public rendezvous: mount registry (SQLite), tunnel proxy (`/m/{code}/...`), auth/admin/access-request routes, TTL sweeps, per-user storage, drop box | **5/10** — sound internally but imports `server` in 3 places (dropbox, user_storage, main) |
| `agent/` | CLI that mounts a folder: connects to relay, runs the server in-process via `httpx.ASGITransport`, reconnect loop with typed non-retryable errors | **4/10** — hard-imports `server` internals (`connection.py:27-29`, `display.py:6-7`); cannot be extracted standalone |
| `client/` | React/TS SPA: file browser, uploads with progress + conflict resolution, previews, share links, scratchpad, admin dashboard, mount-status overlay | **6/10** — clean typed API layer, but all state lives in a 613-line `App.tsx` |

**Core request flow:** browser → relay `mount_proxy.py` (auth + allowlist check, injects
trusted `X-WFS-*` headers) → tunnel frames over the agent's WebSocket → agent replays the
request into an in-process ASGI server → response streams back frame-by-frame.

---

## 2. Strengths (commendable decisions)

1. **Layered security model.**
   - Path traversal: `resolve_safe_path` (`server/app/services/file_service.py:43-73`)
     resolves symlinks then checks `is_relative_to`; search re-validates every rglob hit
     against symlink escapes mid-walk (`file_service.py:249`).
   - Header-spoofing prevention: the server only trusts `X-WFS-*` identity headers when
     relay-served (`server/app/services/relay_identity.py:19-25`); the proxy strips
     inbound spoofed headers before injecting its own (`mount_proxy.py:199-207`). A LAN
     client cannot elevate privileges.
   - bcrypt's silent 72-byte truncation explicitly guarded (`accounts/passwords.py:11-26`).
   - Agent tokens use a separate itsdangerous salt + 120s max-age, so session tokens
     cannot double as agent tokens (`relay/app/services/session.py:80-98`).

2. **Deliberate tunnel backpressure.** Bounded per-stream `asyncio.Queue(maxsize=64)` with
   blocking `put` (`tunnel/connection.py:161-163`); a lagging consumer propagates TCP
   backpressure to the sender instead of ballooning memory. Documented in the docstring.

3. **`typing.Protocol` WebSocket abstraction** (`tunnel/protocol.py`). Relay uses
   FastAPI's WebSocket, agent uses a `websockets` adapter, tests use a mock — all
   structurally, no framework dependency in the core protocol.

4. **Typed exceptions with structured fields everywhere.** `FileConflictError` carries
   `path` + `existing_path` (surfaced in the 409 body), `UsernameTakenError.username`,
   `GroupCycleError.group_id`. No `return None`, no string-parsed errors.

5. **Subtle concurrency correctness.** Agent opens the stream synchronously before
   spawning the handler task so DATA frames cannot race past registration
   (`agent/connection.py:112-115`). Group cycles prevented at write time (BFS,
   `accounts/sqlite_store.py:398`) and defended at read time (DFS with frozenset path,
   `accounts/resolve.py:17-44`).

6. **Operationally mature details:** atomic overwrites via temp + `os.replace`
   (`file_service.py:196-199`); streaming ZIP with eager path validation before headers
   commit; registry startup-cleanup so mount statuses are honest after relay restart
   (`sqlite_registry.py:624-659`); rate-limited auth; single access-control decision point
   (`relay/app/services/access_policy.py:105-146`).

7. **Real test volume:** ~835 test functions across 74 files; `scripts/e2e.sh` spins up a
   throwaway relay + two mounts, seeds accounts, and tests the full
   access-request → approve → access flow across two browser contexts.

8. **Smart frontend touches:** XHR (not fetch) for upload progress with documented
   rationale (`client/src/api/client.ts:89-131`); 3-second "stable connection" gate so WS
   reconnect backoff is not reset by flapping mounts (`useWebSocket.ts:22-27`); polling
   paused on hidden tabs (`useMountStatus.ts:83-93`); `as const` enum pattern throughout.

---

## 3. Weaknesses & Recommended Fixes (by severity)

### A. Real bugs

1. **TTL warnings re-fire forever.** `relay/app/services/ttl_sweep.py:51` sets
   `mount.ttl_warned = True` on a `MountRecord` snapshot that
   `SqliteMountRegistry.active_mounts()` rebuilds from SQLite each sweep; the flag is
   never persisted, so every sweep re-warns every mount in the window.
   **Fix:** `UPDATE mounts SET ttl_warned = 1` after sending the warning.

2. **WS bridge is text-only.** `agent/proxy.py:155,160` always uses
   `send_text`/`receive_text`; any binary WebSocket frame from the local app crashes on
   decode. The protocol's `WS_DATA` frames already carry raw bytes.
   **Fix:** branch on frame type via `receive()` and mirror bytes/text.

3. **`close()` missing from `WebSocketProtocol`.** `tunnel/protocol.py` defines 5 methods,
   but `TunnelConnection.close()` calls `self._ws.close()` (`tunnel/connection.py:481`).
   A conforming implementation without `close()` passes type-checking and fails at
   runtime. **Fix:** add `close()` to the Protocol. Also remove the dead, deprecated
   `asyncio.get_event_loop()` call at `tunnel/connection.py:431`.

4. **Device identity conflation (client).** `useFileRequests.ts:87` passes the display
   name as the device ID, so request ownership is keyed on "Swift Fox"-style names; two
   devices with the same name conflate identity. **Fix:** generate and persist a stable
   UUID device ID in localStorage, separate from the display name.

### B. Swallowed exceptions (violates project rule 11)

Silent `except Exception: pass` in the tunnel glue — exactly where diagnostics matter
most: `agent/proxy.py:183-184,188`, `relay/app/routers/mount_proxy.py:364-365,438-439`,
`relay/app/routers/agent_ws.py:89-90`, and `server/app/main.py:90-91` (swallows config
`RuntimeError`). Client mirrors this with `.catch(() => {})` in `useClipboard.ts`
(98-101, 134-136, 143-145), `useFileRequests.ts:47-49`, `useSearch.ts:73`.
**Why it matters:** when a tunnel bridge dies mid-stream there is no log line, no error
frame — just a hung download. **Fix:** `logger.exception(...)` with stream/mount context
in each; surface client failures as toasts or console errors.

### C. Cross-package coupling blocking reuse

- **server → relay:** `server/app/routers/files.py:110,179` imports
  `relay.app.services.file_ttl_db` inside try/except (failures invisible).
- **relay → server:** `dropbox.py:13-14`, `relay/app/main.py:44`,
  `relay/app/routers/user_storage.py:13-21` import server internals directly.
- **agent → server:** `agent/connection.py:27-29` imports `create_app`/config/auth
  setters; `agent/display.py:6-7` imports QR + LAN-IP helpers for terminal output.

The server⇄relay pair is a cycle in practice; none of `server`, `relay`, `agent` can be
extracted or tested in isolation. **Fixes, in effort order:**
1. Move `qr_service`/`network_service` to `shared/` (kills `agent/display.py` coupling).
2. Agent accepts an app factory `Callable[[], ASGIApp]` passed by the CLI glue instead of
   importing `create_app`.
3. Invert the TTL dependency: define a `FileTtlProvider` protocol in `server/`; relay
   injects its implementation at mount time.

### D. Event-loop blocking in async handlers

`list_directory` (`iterdir`), `search_files` (`rglob`), `delete_paths`
(`shutil.rmtree`), `rename_path`, `create_folder` (all in `file_service.py`), and
`usage_bytes` (`os.walk`, `relay/app/services/user_storage.py:29-38`) run synchronously
inside async routes. One `rglob` over a big tree freezes every concurrent transfer —
including tunnel traffic, since the agent runs this app in-process. Uploads already use
`aiofiles` correctly, making the inconsistency visible.
**Fix:** wrap in `await asyncio.to_thread(...)`.

Related: relay registry and accounts DBs use `journal_mode=DELETE` on single shared
aiosqlite connections (`sqlite_registry.py:136`, `accounts/sqlite_store.py:92`) while the
server correctly uses WAL (`server/app/services/sqlite_store.py:33`). **Fix:** switch to
WAL. Note `FileTtlDb` shares the registry's connection (`relay/app/main.py:58`),
serializing TTL and registry operations.

### E. Singleton dependency injection

At least 9 module-level `_instance` + `get_X()/set_X()` singletons, plus
`app = create_app()` at import time (`server/app/main.py:132`, `relay/app/main.py:193`).
Worst symptom: the agent mutates the server's global config on every connect
(`agent/connection.py:309-323`) — two mounts in one process would conflict. Downstream
encapsulation break: `server/app/routers/share.py:55` reaches into
`service._active_links` directly (and 8 test occurrences mutate it to fake expiry).
**Fix:** build services in the lifespan, attach to `app.state`, have routers declare
dependencies via `Depends`. `ShareLinkService.create_link` should return the full record.

### F. Frontend structure & trust boundaries

- **`App.tsx` is 613 lines** wiring 12+ hooks and all dialog state; props drilled 2–3
  levels. **Fix:** 2–3 Contexts (file browsing, uploads, notifications) along existing
  hook boundaries; no external store needed.
- **WS messages blind-cast** (`useWebSocket.ts:77-98`: `data as DeviceInfo[]` etc.;
  similar in `useClipboard.ts:53,63,68`). **Fix:** zod schemas or hand-rolled guards at
  the WS boundary.
- **No error boundary anywhere** — any render error white-screens the app. **Fix:** one
  `ErrorBoundary` per `pickRoot()` target (`main.tsx:101-108`).
- `apiDelete` always expects JSON, forcing raw `fetch()` workarounds for 204 responses
  (`shares.ts:66-74`, `clipboard.ts:26-36`). `cycleThemeMode` duplicated in `App.tsx:58-67`
  and `DropBoxPage.tsx:37-46`. Upload TTL options are raw strings in `Toolbar.tsx:49-54`
  (contrast `shares.ts` `ShareTTL` const). `AdminDashboard.tsx` (279 lines) has no hook
  abstraction. `serverMode!` non-null assertion at `main.tsx:83`.

### G. Process gaps

- **No CI, no type checking, ruff installed but unconfigured.** 835 tests run only
  manually; type hints unenforced. **Fix:** one GitHub Actions workflow
  (`ruff check` + `uv run pytest` + `tsc --noEmit` + vitest); add `[tool.ruff]`; adopt
  mypy starting with the clean leaf packages (`tunnel`, `accounts`, `shared`).
- **Dead root files contradict the docs:** `network_file_server.py` (old Flask app),
  `start_server.sh`, `main.py` stub, `requirements.txt` (Flask pins), and root
  `run.sh`/`run_relay.sh`/`run_mount_server.sh` overlapping `scripts/run.sh`.
  **Fix:** delete them.
- **Test coverage inverted relative to risk:** tunnel (most critical, most reusable) has
  2 test files; no end-to-end test of the full proxy path
  (browser→relay→agent→server) beyond auth flows; client has one unit test file.
- `relay/app/routers/access_requests.py:35-48`: `_serialize` does N+1 `get_user_by_id`
  lookups per listed request.
- `ShareLinkService._active_links` is a plain dict with no lock (contrast
  `ServerStateStore`'s `threading.RLock`).

---

## Top 5 priorities

1. Fix `ttl_warned` persistence bug + add `close()` to `WebSocketProtocol` (real bugs, <1 hour).
2. Replace every `except: pass` in the tunnel path with logged context.
3. `asyncio.to_thread` the blocking filesystem calls + WAL on relay/accounts DBs.
4. Minimal CI workflow (locks in the 835 tests).
5. Break the server⇄relay cycle via a `FileTtlProvider` protocol (unlocks the modularity goal).

---

**Overall:** the codebase is in good shape for its scope — the security model, tunnel
protocol, and `accounts/` package are stronger than typical hobby-scale projects. The
weaknesses concentrate in glue (singletons, cross-package imports, swallowed exceptions)
rather than core logic — debt that is still cheap to pay down.

## File size reference (largest files)

| File | ~Lines |
|---|---|
| `relay/app/services/sqlite_registry.py` | 660 |
| `client/src/App.tsx` | 613 |
| `tunnel/connection.py` | 484 |
| `server/app/services/sqlite_store.py` | 443 |
| `relay/app/routers/mount_proxy.py` | 440 |
| `accounts/sqlite_store.py` | 420 |
| `agent/connection.py` | 412 |
| `server/app/routers/files.py` | 407 |
| `server/app/services/file_service.py` | 405 |
| `relay/app/routers/agent_ws.py` | 376 |
| `client/src/pages/AdminDashboard.tsx` | 279 |
