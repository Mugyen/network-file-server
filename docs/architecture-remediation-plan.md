# Architecture Remediation Plan

Source: critical architecture review (2026-06-10). Each phase is implemented,
tested, and committed atomically, in order. Done-when criteria are binding:
a phase is not complete until its tests pass and the full suite is green.

Global invariants for every phase:
- Full gate green: `uv run ruff check .`, `uv run mypy`, `uv run python -m pytest`,
  and (when client touched) `npm run lint && npm run typecheck && npm run test:unit`.
- `docs/project-log.md` entry per phase; README/scripts updated when run/test
  instructions change.
- No silent exception swallows; domain exceptions over None-returns; enums over
  string modes (project rules 2, 4, 11).

---

## Phase 1 — Centralized exception handling (server + relay)

**Problem.** Four coexisting error patterns: central `@app.exception_handler`
for 2 exceptions (`server/app/main.py:107-120`); per-route try/except returning
ad-hoc `JSONResponse` (`server/app/routers/files.py:53-76`); catch-and-rewrap
into `HTTPException` (`routers/clipboard.py`); direct `HTTPException` raises
(`routers/auth.py`). The relay defines a clean taxonomy in
`relay/app/exceptions.py` then catches it locally in every router.

**Why it matters.** A forgotten catch in a future router turns an intended
404/410/503 into a 500. Error response shapes differ between routers. Every
route pays try/except boilerplate for what the framework centralizes.

**Solution.** One `register_exception_handlers(app)` function per package
(`server/app/error_handlers.py`, `relay/app/error_handlers.py`) mapping every
domain exception to `(status, {"detail": ...})`. Routers raise domain
exceptions and never construct error responses. Delete the local try/excepts.

**Why this solution.** FastAPI-native (`app.exception_handler`), single source
of truth for the status mapping, zero new dependencies, and it shrinks every
router. The mapping table itself becomes testable in isolation.

**Files.** New: `server/app/error_handlers.py`, `relay/app/error_handlers.py`.
Modified: both `main.py`s, `server/app/routers/{files,clipboard,auth}.py`,
relay routers that catch domain exceptions (`mount_proxy` keeps its HTML error
pages — proxy errors are user-facing pages, not JSON; only JSON paths migrate).

**Tests.** Unit tests asserting each exception maps to its documented status;
existing route tests already pin statuses and must stay green unchanged.

**Done when.** No router catches a domain exception just to set a status code;
full suite green.

---

## Phase 2 — Kill module-level singletons (relay app.state; server store DI)

**Problem.** Relay holds 7 module-level mutable globals with 11 getter/setters
(`config.py:206`, `mount_registry.py:188`, `session.py:125`,
`account_store.py:10`, `file_ttl_db.py:124`, `dropbox.py:15-16`,
`agent_ws.py:65`). The server, despite its "no module-level singletons"
docstring, caches stores in `_stores: dict[Path, ServerStateStore]`
(`server/app/services/sqlite_store.py:432`).

**Why it matters.** Two app instances cannot coexist in one process; test
teardown is a manual choreography of `set_*(None)` calls; a mid-sequence
failure poisons subsequent tests; the dropbox fixture in
`tests/relay/test_dropbox.py` demonstrates the cost today.

**Solution.** A `RelayState` dataclass built in lifespan and attached to
`app.state`; accessors in `relay/app/dependencies.py` via `Depends`. Delete
the getter/setter pairs. Server: `create_app` constructs one
`ServerStateStore` and passes it to services explicitly; delete the `_stores`
cache and `get_state_store()`.

**Why this solution.** It is the pattern the server already uses and documents;
lifecycle becomes explicit in lifespan; tests construct apps via the factory
and get isolation for free. No new dependencies.

**Files.** `relay/app/{config,main,dependencies}.py`, relay services/routers
that call `get_*()`, `server/app/services/{sqlite_store,upload_index,clipboard_service,share_service,file_request_service}.py`,
`server/app/main.py`, plus relay test fixtures.

**Tests.** New regression test: building two relay apps (or two server apps on
different data dirs) in one process yields independent state. Existing suite
must pass with fixtures migrated to factory-built apps.

**Done when.** `grep` finds no module-level mutable `_x: T | None = None`
service singletons in `relay/app` or `server/app`; suite green.

---

## Phase 3 — Server SQLite goes async; shared sqlite kernel

**Problem.** `ServerStateStore` is sync `sqlite3` + `threading.RLock`
(`sqlite_store.py:31,77`) called directly from `async def` services — every
clipboard/share/upload-owner query stalls the event loop.
`upload_index.py:18-35` is false-async (async defs, zero awaits). Three
sqlite layers (server sync, relay aiosqlite, accounts aiosqlite) re-implement
connection setup/WAL/schema-init.

**Why it matters.** Under concurrent requests the event loop blocks on disk
I/O; latency compounds. False-async misleads callers and reviewers.
Triplicated connection/bootstrap code violates reuse (project rule 8).

**Solution.** Migrate `ServerStateStore` to `aiosqlite`; services `await` the
store; `upload_index` becomes genuinely async. Extract
`shared/sqlite_kernel.py`: `open_db(path)` (aiosqlite connect + WAL + foreign
keys), a transaction context manager, and a `run_schema(db, ddl)` helper —
adopted by all three stores.

**Why aiosqlite (existing dep, not new).** Already used by relay and accounts —
this is consistency, not addition. It runs SQLite calls on a dedicated worker
thread behind an async API, so the event loop never blocks. Alternative
considered: `asyncio.to_thread` wrappers — rejected because it keeps a second
concurrency idiom alive and leaves the RLock dance in place.

**AS-IMPLEMENTED DEVIATION (2026-06-10).** The server store stays sync
sqlite3; the *service layer* offloads via `asyncio.to_thread`. Reason
discovered during implementation: ``create_app`` is a synchronous factory
(services query SQLite at construction — share secret, link preload) and the
~900-test suite drives apps through lifespan-less ``httpx.ASGITransport``;
a fully-async store would force lifespan-based construction and a relay-
phase-2-sized test migration for no additional event-loop benefit. The
threading contract is documented in sqlite_store.py. The kernel
(`shared/sqlite_kernel.py`) unifies the two genuinely-async relay stores;
``accounts/`` keeps its own bootstrap — the import-boundary rule (leaf
packages import no project packages, shared included) outweighs 8 lines of
reuse.

**Files.** `server/app/services/sqlite_store.py` (rewrite), its five call
sites, new `shared/sqlite_kernel.py`, then `relay/app/services/{sqlite_registry,file_ttl_db}.py`
and `accounts/sqlite_store.py` adopt the kernel (mechanical).

**Tests.** Existing store/service tests migrate to async; new kernel unit
tests (WAL on, txn rollback on error, schema idempotency).

**Done when.** No sync `execute()` reachable from a request handler; kernel
used by all three stores; suite green.

---

## Phase 4 — Tunnel protocol hardening

**Problem.** (a) No protocol version negotiation — the handshake
(`relay/app/routers/agent_ws.py:82-173`) exchanges no version; the first new
`FrameType` breaks deployed agents silently. (b) OPEN/WS_OPEN metadata JSON is
unvalidated on both ends — no size cap before `serialize_frame()`
(oversized headers → `FrameTooLargeError` escaping the endpoint) and the agent
does direct-subscript access on parsed dicts. (c) Heartbeat is one-directional
(relay pings; agent deliberately doesn't — `agent/connection.py:335`), so a
half-dead relay socket leaves the agent believing it is mounted. (d) Relay
`send_open/send_data` calls have no error wrapping — a stale socket crashes
the proxy endpoint instead of returning 503.

**Why it matters.** These are the failure modes of the product's spine. Version
negotiation in particular costs ~20 lines today (zero deployed skew) and is
unpayable debt later.

**Solution.** (a) `PROTOCOL_VERSION` constant in `tunnel/constants.py`; agent
sends it in `agent_auth`; relay rejects incompatible versions with an explicit
close reason. (b) `RequestMetadata` dataclass in `tunnel/` with
`to_payload()/from_payload()` enforcing a size cap (16 KiB) and validating
required fields, raising typed errors — used by both relay and agent. (c)
Agent starts its own 30s heartbeat after registration. (d) Wrap relay
send-paths; convert transport failures to a `TunnelSendError` handled as 503.

**Why no new library.** stdlib `json` + `dataclasses` suffice; the protocol is
small and bespoke — pulling in a serialization framework adds surface, not
safety.

**Files.** `tunnel/{constants,frames or new metadata module,connection,exceptions}.py`,
`agent/connection.py`, `relay/app/routers/{agent_ws,mount_proxy}.py`.

**Tests.** Version-mismatch handshake rejection; metadata round-trip + cap +
malformed-payload tests; heartbeat-both-ways test; send-failure → 503 test.

**Done when.** A version-skewed agent is refused cleanly; oversized/malformed
metadata cannot crash either end; suite green.

---

## Phase 5 — Proxy data plane hardening (HTML rewriter)

**Problem.** `mount_proxy.py:268-285` buffers entire `text/html` bodies with
no size cap and hard-decodes UTF-8 (`b"".join(...).decode("utf-8")`) — any
non-UTF-8 page (or mislabeled content) raises mid-request and crashes the
proxy.

**Why it matters.** A proxy must degrade, not die, on hostile or odd content.
The rewrite feature (asset paths → `/m/{code}/…`) is cosmetic; serving
unrewritten bytes is strictly better than a 500.

**Solution.** Extract `relay/app/services/html_rewriter.py`:
charset detection from Content-Type (`charset=` param, default utf-8), decode
with fallback — on `UnicodeDecodeError`/`LookupError` return the original bytes
unmodified; a buffer cap (`HTML_REWRITE_MAX_BYTES = 5 MiB`, enum-free constant)
— when Content-Length exceeds it or the cap is hit mid-buffer, skip rewriting
and stream what was buffered plus the remainder unchanged.

**Why this solution.** Keeps the rewrite for the common case (small SPA shells)
while making the worst case a passthrough. Streaming regex-rewrites across
chunk boundaries were considered and rejected: tag-split-across-chunks
complexity isn't warranted for a cosmetic rewrite.

**Files.** New `relay/app/services/html_rewriter.py`; `mount_proxy.py` shrinks.

**Tests.** Unit tests: charset variants, undecodable bytes passthrough, cap
exceeded passthrough, rewrite correctness (moves existing tests).

**Done when.** No naked `.decode("utf-8")` in the proxy path; rewriter has its
own test file; suite green.

---

## Phase 6 — Dropbox becomes a first-class mount kind

**Problem.** The dropbox's wiring spans three files: post-hoc TTL-provider
injection (`relay/app/main.py:68`), shutdown that derefs the client but never
closes the app, and `mount_proxy.py` string-comparing the dropbox code twice
(HTTP ~line 133, WS ~line 326) with a dedicated WS bridge loop just for it.

**Why it matters.** Every proxy feature must be written twice (tunnel path +
dropbox path) or the dropbox silently misses it. Special cases that exist
because of plumbing, not domain, are pure tax.

**Solution.** `MountKind` enum (`TUNNEL`, `LOCAL_ASGI`) on the registry
record. A `LocalAsgiMount` object (app + httpx client + lifecycle close())
constructed in lifespan and registered like any mount. The proxy dispatches on
kind; the two code-equality checks and the bespoke WS loop are deleted.

**Why this solution.** The registry already models "a mount"; the dropbox is
one. Unifying restores single-code-path semantics and gives the dropbox a real
shutdown.

**AS-IMPLEMENTED DEVIATION (2026-06-10).** No persisted MountKind enum
column: a live ASGI app cannot be persisted, and the registry already
encodes locality as ``connection=None``. The live object lives in
``RelayState.local_mounts`` (LocalAsgiMount: app + client + WS bridge +
aclose); membership in that map IS the mount kind, and the proxy dispatches
on it with zero drop-box-specific code.

**Files.** `relay/app/services/{mount_registry,sqlite_registry,dropbox}.py`,
`relay/app/routers/mount_proxy.py`, `relay/app/main.py`.

**Tests.** Existing dropbox tests must pass unchanged (behavioral contract);
new test: dropbox appears in registry with kind LOCAL_ASGI; shutdown closes it.

**Done when.** `grep dropbox relay/app/routers/mount_proxy.py` returns nothing;
suite green.

---

## Phase 7 — Explicit trust boundary (signed identity headers; legacy enum)

**Problem.** The relay injects identity as plain headers
(`X-WFS-User/-Role/-Auth-Bypass`, `mount_proxy.py:211-214`); the mounted
server trusts them solely because `config.mount_code` is set — sound only
while the tunnel is the *only* path to the server, which nothing enforces.
Separately, `access_policy.py:118-123` fails open when no policy row exists
(pre-v1.3 mounts) — load-bearing behavior expressed as an exception catch.

**Why it matters.** An agent whose local port is reachable on the LAN accepts
forged identity headers. The fail-open is invisible to future maintainers.

**Solution.** Per-mount HMAC: the agent generates a secret at startup, passes
it to its composed server app (config) and to the relay in `agent_auth`; the
relay signs the identity headers (`X-WFS-Identity-Sig` = HMAC-SHA256 over
user|role|bypass|request-path); server middleware verifies before trusting.
stdlib `hmac`/`hashlib` — no new library. For access policy: add
`AccessMode.LEGACY`; startup migration inserts explicit LEGACY rows for
policy-less mounts; the fallback catch becomes a logged, enum-visible state.

**Files.** `agent/{cli,connection,auth}.py`, `server/app/{config}.py`,
`server/app/services/relay_identity.py`, `server/app/middleware/auth_middleware.py`,
`relay/app/routers/{agent_ws,mount_proxy}.py`, `relay/app/services/access_policy.py`.

**AS-IMPLEMENTED DEVIATIONS (2026-06-10).**
- Signature covers `user|role|bypass`, NOT the request path. Path-binding was
  dropped: the path is rewritten between relay and server (fragile to
  canonicalize), and per-mount secrets already prevent cross-mount replay;
  intra-mount replay requires capturing a legitimate signed request = local
  MITM = already-compromised host (out of scope). Shared canonicalization
  lives in `shared/identity_sig.py` so relay (signer) and server (verifier)
  stay byte-identical.
- The per-mount secret lives in `SqliteMountRegistry._identity_secrets`
  (in-memory, never persisted — agents mint a fresh secret per connect),
  not in a registry DB column.
- A LATENT HOLE was found and closed during implementation: `AuthMiddleware`
  did its own raw `x-wfs-auth-bypass == "1"` check, bypassing signature
  verification entirely. It now routes through `is_auth_bypassed` (config +
  HMAC) like the rest of the trust path.
- LEGACY: rather than a startup migration inserting rows, the pre-v1.3
  `access_mode` ALTER default is `'legacy'` (fresh mounts get an explicit
  policy anyway); `authorize` treats LEGACY as OPEN but logs it. The
  `MountNotFoundError` fail-open is now logged with an accurate "mount
  vanished → get_connection renders 404" comment.

**Tests.** Forged-header rejection (wrong/missing sig → anonymous), happy-path
signed identity, legacy-mount migration test.

**Done when.** Identity headers without a valid signature are ignored; legacy
mounts are explicit rows; suite green.

---

## Phase 8 — Composition cleanups

**Problem.** (a) `server/app/cli.py` (316 lines) mixes arg parsing, config
build, QR display, uvicorn boot, and agent wiring. (b) `agent/connection.py`
keeps two custom receive loops that bypass `TunnelConnection.run_receive_loop`
and poke `conn._ws`/`conn._dispatch_frame`. (c) `mount_proxy.py` remains large
after phases 5–6.

**Solution.** (a) Split: `cli.py` (parsing only) + `server/app/bootstrap.py`
(compose & run; the agent-facing `build_mount_app` moves here; boundaries-test
whitelist updated to the new composition root). (b) `TunnelConnection.run_receive_loop`
gains optional `on_open`/`on_ws_open` callbacks; both agent loops are deleted.
(c) Final extraction pass on mount_proxy if still >250 lines.

**Why this solution.** Composition becomes testable without argv; frame
routing logic lives in exactly one place (protocol changes touch one loop, not
three).

**Tests.** Existing CLI tests split accordingly; receive-loop tests move to
tunnel-level callback tests; agent integration tests must pass unchanged.

**Done when.** No agent code touches `conn._*` internals; cli.py is parsing +
delegation only; suite green.

**AS-IMPLEMENTED (2026-06-10).** (a) `server/app/bootstrap.py` is the new
composition root (`build_mount_app`, `run_mount_agent`, `run_lan_server`);
`cli.py` is parsing + delegation; boundaries whitelist points at bootstrap.
(b) `TunnelConnection.run_receive_loop_with_handlers(on_open, on_ws_open)`
added (private `_run_receive_loop` core; no default params per project rule —
the relay's zero-arg `run_receive_loop()` is the other wrapper). The agent's
two hand-rolled loops are deleted; `_OpenFrameHandlers` owns task
spawn/drain and `expired_files` moves to a registered control handler — the
agent no longer touches `conn._ws`/`conn._dispatch_frame`. (c) NOT done:
mount_proxy is 520 lines but cohesive (two tunnel-forwarding endpoints +
shared header injection); the high-value extractions (html_rewriter,
local-mount WS bridge) already landed in phases 5-6. A further split was
judged to add indirection without clear benefit. e2e (`scripts/e2e.sh`)
deferred to CI — it needs a browser + built client; the real-tunnel
integration suite (`tests/integration/test_full_path.py`) passes as the
local integration signal.

---

## Phase 9 — Client API types generated from OpenAPI

**Problem.** Hand-written response types (`client/src/types/*`) silently drift
from `server/app/models/schemas.py`; nothing fails at build time when the
backend changes. Base-path handling is duplicated across API modules.

**Solution.** Generate types from the server's OpenAPI schema and consolidate
HTTP access into one typed client module.

**New library: `openapi-typescript` (devDependency).** What it offers:
generates a single `.d.ts`/`.ts` of request/response types from OpenAPI 3.x
JSON; zero runtime footprint (types only); one command, no config.
Why it over alternatives: `openapi-generator` (Java toolchain, heavyweight
client codegen we don't need), `orval` (generates runtime clients + adds
fetch wrappers — we keep our thin `apiFetch`). We only need *types*; the
lightest tool that does exactly that wins.

**Wiring.** `scripts/gen_api_types.sh`: dump schema via a tiny
`server/app/openapi_dump.py` (`create_app(...).openapi()` → JSON) then
`npx openapi-typescript openapi.json -o client/src/types/api.gen.ts`.
CI: regenerate and `git diff --exit-code` so drift fails the build.
Existing hand-written types become aliases into the generated namespace, then
are removed where trivially replaceable.

**Tests.** `tsc` is the test: a backend schema change without regen fails CI.

**Done when.** Generated types exist, CI drift-check runs, at least the
files/clipboard/share APIs consume generated types; client gate green.

---

## Phase 10 — Client server-state layer + centralized routing

**Problem.** Mutations manually call `loadFiles()`; WebSocket pushes race HTTP
refetches (double refetch, transiently stale UI); three nested providers fetch
independently with no dedup/invalidations. Routing is three mechanisms:
`pickRoot()` string-matching (`main.tsx:111`), a probe-fetch in `Root`, and
module-load-time `window.location` reads in `remoteMount.ts`.

**Solution.**
(a) **New library: `@tanstack/react-query` (runtime dependency).** What it
offers: request deduplication, cache with `staleTime`, declarative
invalidation (`invalidateQueries`), mutation lifecycle, retry/backoff,
devtools. Why it over hand-rolling: the review's race conditions *are* cache
coherence bugs; React Query's semantics (dedup in-flight requests, invalidate
on mutation, reconcile pushed updates via `setQueryData`) are exactly the
missing layer, battle-tested at ~13 kB gzip. A hand-rolled
`ServerStateVersion` context was considered and rejected: it reimplements the
hard 20% (dedup, staleness, races) without devtools or ecosystem familiarity.
Plan: `QueryClientProvider` at root; `useQuery` for files/clipboard/shares/
file-requests keyed by path; mutations + WS handlers invalidate or
`setQueryData`; BrowseContext keeps UI state (selection, path) only.
(b) Routing: `enum AppMode` resolved once in a single `resolveAppMode()`
(pathname + probe), replacing `pickRoot` and scattered location reads. No
router library — four static pages don't justify react-router; the problem is
scattered decisions, not missing route features.

**Tests.** Vitest: query-hook tests with mocked fetch (dedup, invalidate-on-
mutate); mode-resolution unit tests. Existing Playwright e2e must pass.

**Done when.** No manual `loadFiles()` after mutations; one mode decision
point; client gate + e2e green.

---

## Phase 11 — Client hook test coverage

**Problem.** The hardest client state machines have zero unit tests:
`useWebSocket` (reconnect/backoff), `useUpload` (concurrency/conflicts),
`useClipboard` (debounce + WS sync). Coverage is inverted toward trivial utils.

**Solution.** Vitest + fake timers + a hand-rolled `MockWebSocket` (no new
library — `msw` was considered and rejected: it mocks HTTP, our gap is WS and
timer logic; `vi.stubGlobal` covers fetch). Tests: backoff schedule and
stable-connection reset; upload queue concurrency cap + conflict-resolution
enum paths; clipboard debounce coalescing + WS-pushed updates reconciling
against local edits.

**Done when.** Each of the three hooks has happy-path, edge, and failure-mode
tests; client gate green.

---

## Sequencing & verification

Order: 1 → 2 → 3 (mechanical backend) → 4 → 5 (protocol/data plane) → 6 → 7
(structural/security) → 8 (cleanup) → 9 → 10 → 11 (client). Each phase: own
commit(s), project-log entry, full gate. After phase 8 and again after 11:
`./scripts/e2e.sh` (Playwright through a real tunnel) as the integration gate.
