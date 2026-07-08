# Codebase Review - 2026-07-08

Audit-only review of `/home/rahul/Projects/network-file-server`. No product-code fixes were made.

## Repo Overview

This repository is a Python/FastAPI file-sharing system with three main runtime modes:

- `server/`: LAN and embedded mount server. Owns file APIs, password auth, share links, clipboard, file requests, upload ownership, SPA serving, and trusted relay identity verification.
- `relay/`: public relay service. Owns mount registry, account/session/admin APIs, optional OIDC, access requests, mount proxying, drop box local mount, rate limiting, and TTL sweeps.
- `agent/` and `tunnel/`: relay mount client plus binary multiplexing protocol for HTTP and WebSocket traffic.
- `accounts/` and `shared/`: framework-free account primitives and shared helpers.
- `client/`: Vite/React SPA with unit tests and Playwright e2e specs.

The project has strong recent remediation work: import-boundary tests, app-scoped server state, SQLite/WAL persistence, signed identity headers, generated OpenAPI client types, React Query state, and CI gates. The largest remaining risks are now edge-case authorization/path-safety gaps around newer feature intersections rather than broad structural problems.

## Commands Run

- `rg --files`
  - Mapped repository files; used first per instruction.
- `git status --short`
  - Result before report creation: `?? docs/tailscale-overlay-plan.md` only.
- `git rev-parse --show-toplevel`
  - Confirmed repo root: `/home/rahul/Projects/network-file-server`.
- `sed -n '1,220p' README.md`, `sed -n '1,240p' pyproject.toml`, `sed -n '1,220p' client/package.json`, `sed -n '1,220p' docs/project-log.md`
  - Reviewed run/test conventions, dependencies, and project-log style.
- `sed -n '1,220p' scripts/test.sh`, `scripts/build.sh`, `scripts/e2e.sh`, `scripts/run.sh`
  - Reviewed standard wrappers.
- `test -d client/node_modules`, `test -d .venv`
  - Both present.
- `uv run ruff check .`
  - Passed: `All checks passed!`
- `uv run mypy`
  - Passed: `Success: no issues found in 26 source files`.
- `uv run --group dev python -m pytest tests/test_import_boundaries.py tests/accounts tests/tunnel tests/shared server/tests/test_config.py server/tests/test_auth.py tests/relay/test_access_policy.py tests/relay/test_secure_cookies.py -q`
  - Passed: `219 passed, 6 warnings in 65.27s`.
  - Warnings were httpx per-request cookie deprecations.
- `npm run lint`, `npm run typecheck` from `client/`
  - Blocked locally: `/bin/bash: line 1: npm: command not found`.
  - `node` exists at `/usr/bin/node`, but `npm` is absent from this shell PATH.
- `uv run --group dev python -m pytest server/tests/test_upload.py server/tests/test_share.py server/tests/test_receive_uploads.py server/tests/test_receive_mode.py -q`
  - Passed: `41 passed, 1 warning in 8.12s`.
- Multiple targeted `rg -n` and `nl -ba` reads across `server/`, `relay/`, `agent/`, `tunnel/`, and `client/src/` to inspect high-risk paths.
- `git ls-files client/test_fix.txt ...`, `file client/test_fix.txt`, `nl -ba client/test_fix.txt`
  - Confirmed `client/test_fix.txt` is tracked and contains only `test upload after fix`.

## Prioritized Findings

### 1. Critical: Uploaded filenames can escape the target directory

`upload_file()` validates the destination directory but not the uploaded filename before joining it into the filesystem path. A multipart client controls `UploadFile.filename`, and values such as `../escape.txt`, `subdir/escape.txt`, or absolute-looking names are not passed through `_validate_name()` or a safe-path resolver before writes.

Evidence:

- `server/app/services/file_service.py:99` defines `_validate_name()`, but `upload_file()` does not call it.
- `server/app/services/file_service.py:160` validates only `relative_dir`.
- `server/app/services/file_service.py:162-203` uses `upload.filename` directly in `destination = target_dir / filename`, overwrite checks, temp path creation, and final write/replace.
- The same helper is exposed through normal uploads at `server/app/routers/files.py:123-126`, PWA share-target uploads at `server/app/routers/share_target.py:66-72`, file-request fulfillment at `server/app/routers/file_requests.py:78-83`, drop box relay paths via the same server router, and per-user relay storage at `relay/app/routers/user_storage.py:104-106`.

Impact:

- Write outside the selected upload directory and potentially outside the shared root, depending on process permissions and filename path components.
- Poison upload ownership/TTL records with paths that do not match the actual write target.
- In relay user storage, this can break per-user isolation because the shared helper is reused under each user's data directory.

Proposed solution:

- Add a public helper such as `validate_upload_filename(filename: str) -> str` in `server/app/services/file_service.py`.
- Reject empty names, path separators (`/` and `\`), `.`/`..`, null bytes, and absolute paths. Consider normalizing browser-supplied Windows paths by taking `Path(filename).name` only if product requirements prefer salvage over rejection; for strict contracts, reject.
- Call this helper at the start of `upload_file()` and use the returned basename everywhere.
- Add pytest coverage in `server/tests/test_file_service.py`, `server/tests/test_upload.py`, `server/tests/test_share_target.py`, and `tests/relay/test_user_storage.py` for `../x`, `a/b.txt`, `..\\x`, absolute paths, and null bytes.

### 2. Critical: Share-link APIs bypass read-only and RECEIVE role restrictions

The share-link router has no mode/role dependencies. Creating a share link is a state-changing operation that also creates a public unauthenticated download path. In read-only or RECEIVE-scoped relay access, this lets users expose arbitrary known files even when other file operations are restricted.

Evidence:

- `server/app/routers/share.py:34-54` creates a link after only checking that `body.file_path` exists; it does not call `require_write_access`, `require_full_access`, or `receive_scope_user`.
- `server/app/routers/share.py:67-89` lists all active share links without mode/role scoping.
- `server/app/routers/share.py:92-101` revokes links without mode/role scoping.
- `client/src/components/FileRow.tsx:174-183` shows the Share button for files regardless of `readOnly`.
- `client/src/components/HeaderActions.tsx:63-70` always exposes the Share Links panel.
- Existing read-only tests cover uploads, rename, delete, folders, clipboard, and file requests, but not shares (`server/tests/test_read_only.py:10-174`). Existing receive tests do not cover `/api/shares` (`server/tests/test_receive_mode.py:1-114`, `server/tests/test_receive_uploads.py:1-162`).

Impact:

- READ/RECEIVE users can create public links to files they are not supposed to redistribute.
- RECEIVE users can submit arbitrary `file_path` values by path guessing; `resolve_safe_path()` confirms existence but does not apply ownership scoping.
- Users can revoke other active share links.

Proposed solution:

- Decide the product policy explicitly. The safer default is:
  - `POST /api/shares`: `Depends(require_write_access)` and `Depends(require_full_access)`.
  - `DELETE /api/shares/{token}`: `Depends(require_write_access)` and `Depends(require_full_access)`.
  - `GET /api/shares`: `Depends(require_full_access)` unless links are owner-scoped in persistence.
- If RECEIVE users should be able to share only their own uploads, add link ownership metadata and validate with `upload_index.is_owned_by()` before creation/list/revoke.
- Hide Share and Share Links controls in read-only/receive UI modes unless the backend policy allows them.
- Add pytest coverage for read-only mode, global receive mode, and signed relay RECEIVE role headers.

### 3. High: RECEIVE-scoped users can bypass own-upload filtering through ZIP download

`require_browse_access()` explicitly allows relay RECEIVE roles into browse endpoints, but its docstring says endpoints must filter to the user's own uploads. `download_zip()` does not do that filtering.

Evidence:

- `server/app/middleware/mode_guard.py:53-61` says RECEIVE is allowed through browse endpoints and callers must filter list/download/preview/search/zip.
- `server/app/routers/files.py:181-185` enforces ownership for single download.
- `server/app/routers/files.py:288-292` enforces ownership for preview.
- `server/app/routers/files.py:270-272` returns empty search results for RECEIVE.
- `server/app/routers/files.py:200-213` creates a ZIP from `body.paths` without checking `receive_scope_user()`.
- `server/tests/test_receive_uploads.py:84-115` covers single download/preview, but no RECEIVE ZIP case. `server/tests/test_receive_mode.py:106-114` only covers global LAN receive mode, where `require_browse_access()` blocks before the route.

Impact:

- A RECEIVE-scoped relay user who knows or guesses a path can download other users' uploads or pre-existing files as a ZIP.

Proposed solution:

- In `download_zip()`, call `receive_scope_user(request)`.
- If non-`None`, require every requested path to be owned by that user before creating the ZIP; return 404 for any unowned path to avoid disclosing existence.
- Add tests for mixed owned/unowned ZIP requests under signed RECEIVE headers.

### 4. High: Agent WS_OPEN stream registration has a first-message race

The HTTP OPEN path registers the stream before spawning the handler, but the WS_OPEN path registers inside the spawned handler. If the relay sends WS_DATA immediately after WS_OPEN, the agent receive loop can dispatch WS_DATA before the handler has called `open_stream()`. `_dispatch_frame()` silently ignores frames for missing streams, so the first browser message can be lost.

Evidence:

- HTTP path opens before spawn at `agent/connection.py:119-123`.
- WS path only spawns at `agent/connection.py:126-135`; it does not open the stream first.
- `handle_ws_open_frame()` opens the stream later inside the task at `agent/proxy.py:147-148`.
- Missing stream frames are silently ignored in `tunnel/connection.py:165-172`.
- Integration coverage exercises a normal WS ping after initial server push (`tests/integration/test_full_path.py:164-186`), but does not force WS_DATA immediately behind WS_OPEN.

Impact:

- Intermittent lost first WebSocket messages in relay mode, most visible for clients that send immediately on open or for future richer WS features.

Proposed solution:

- Move `conn.open_stream(ws_id)` into `_OpenFrameHandlers.on_ws_open()` before `asyncio.create_task(...)`, mirroring `on_open()`.
- Remove the duplicate `conn.open_stream(ws_id)` from `handle_ws_open_frame()` or make the handler require the stream to already exist.
- Add a unit test that feeds WS_OPEN and WS_DATA back-to-back into `run_receive_loop_with_handlers()` and asserts the WS_DATA reaches the handler queue.

### 5. Medium: Relay proxy leaks tunnel stream slots on early error and timeout paths

`proxy_request()` and `proxy_websocket()` open tunnel streams, then return on several early failures without removing/closing the local stream state. `TunnelConnection` has a hard `MAX_STREAMS` of 100, so repeated oversized-header, stale-send, or first-byte-timeout cases can exhaust the mount connection until it reconnects.

Evidence:

- HTTP proxy opens a stream at `relay/app/routers/mount_proxy.py:244-245`.
- On `MetadataTooLargeError` or `TunnelSendError`, it returns at `relay/app/routers/mount_proxy.py:259-266` without `remove_stream()` or local close.
- On `FirstByteTimeoutError`, it returns at `relay/app/routers/mount_proxy.py:268-276` without cancel/removal.
- WS proxy opens a stream at `relay/app/routers/mount_proxy.py:440-441`; if `send_ws_open()` fails, it closes the browser socket at `relay/app/routers/mount_proxy.py:451-456` but does not remove the stream.
- Stream removal normally happens only when `read_stream_iter()` drains or observes closure at `tunnel/connection.py:474-516`.
- The hard concurrent stream cap is `MAX_STREAMS = 100` at `tunnel/constants.py:12-13`.

Impact:

- A small number of repeated timeout/error requests can consume stream slots and produce follow-on `StreamLimitError` failures for unrelated users.

Proposed solution:

- Wrap opened-stream proxy work in `try/finally` that removes the stream when no `StreamingResponse` generator owns it.
- On first-byte timeout, send `CANCEL` best-effort and then `remove_stream()`.
- For WS_OPEN send failures, call `conn.remove_stream(ws_id)` before returning.
- Add relay tests asserting `remove_stream()` or equivalent cleanup happens on metadata-too-large, send-failed, and first-byte-timeout paths.

## Low-Risk Follow-Up Fixes

- `client/src/components/ShareLinksPanel.tsx:46-53` calls `navigator.clipboard.writeText()` directly instead of the existing `copyToClipboard()` fallback used by `ShareDialog` and `SnippetCard`. This regresses HTTP-over-LAN copy behavior on mobile/non-secure contexts.
- `client/test_fix.txt:1` is a tracked scratch file containing only `test upload after fix`; remove it in a hygiene PR if it is not intentionally part of tests.
- `server/app/services/connection_manager.py:79-84` and `server/app/services/connection_manager.py:92-98` drop dead WebSocket sends without logging. That is acceptable for cleanup but makes real serialization/connection bugs hard to diagnose; add debug logging with device id and exception repr.
- `agent/connection.py:452-456` retries after any unexpected exception without logging the exception. Add debug/exception logging before backoff so field failures are diagnosable.
- `relay/app/routers/mount_proxy.py:234` and `relay/app/routers/user_storage.py:93` parse `Content-Length` with raw `int(...)`; malformed values can become 500s. Convert to explicit 400 or ignore invalid/missing length.
- `relay/app/services/file_ttl_sweep.py:69-71` has no outer exception guard. A DB or broadcast failure can kill the background task; mirror the mount TTL sweep's per-iteration logging pattern.
- Type strictness is strongest in `tunnel`, `accounts`, and `shared`; server/relay/agent still use broad `Any` return types in public routers and helpers. Incremental mypy expansion would catch several contract gaps.

## Residual Risks And Gaps

- I did not run the full pytest suite because the user requested reasonable fast checks and to avoid long-running commands. The targeted Python checks passed.
- I could not run client lint/typecheck/unit tests locally because `npm` is not available in this shell despite `node` and `client/node_modules` being present.
- I did not run Playwright e2e; the wrapper builds the client and starts a relay plus mounts, so it is intentionally slower.
- I did not perform live browser UI inspection.
- I reviewed high-risk paths manually but did not fuzz multipart filenames, tunnel frames, or relay proxy headers.
- No product-code fixes were made; all fixes above remain proposals.

