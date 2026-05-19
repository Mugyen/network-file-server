# Modularity Audit: Network File Server

## Context

The codebase has 4 Python packages (`server`, `agent`, `relay`, `tunnel`) plus a React/TypeScript frontend (`client`). This audit evaluates whether modules are independent enough to be plugged into other projects, and where coupling prevents that.

---

## Overall Score: 7.5/10

The architecture is well-layered with clean dependency flow and no circular imports. Several modules (tunnel, individual services) are genuinely reusable today. The main gaps are: empty `__init__.py` files that don't declare public interfaces, global singleton state for dependency injection, cross-package imports that prevent standalone extraction of the agent, and a few misplaced utilities.

---

## What's Already Good

### 1. `tunnel/` — Gold standard (10/10 reusability)
- Zero dependencies on any other package in this project
- Clean `__init__.py` with re-exports and `__all__`
- Pure WebSocket multiplexing protocol — drop into any project as-is
- Own exception hierarchy (`TunnelError` base + specific subtypes)
- ABC protocol interface (`WebSocketProtocol`) decouples from framework WebSocket impls

### 2. Service layer isolation (`server/app/services/`)
- `file_service.py` — pure async file I/O with path safety. Takes `Path` args, returns Pydantic schemas. No FastAPI imports.
- `auth_service.py` — pure bcrypt + itsdangerous. Zero framework dependencies.
- `share_service.py` — self-contained token signing/validation with own exception types.
- `persistence.py` — generic atomic JSON read/write. Fully reusable.
- `network_service.py` — pure `socket` + `ifaddr` LAN detection. Reusable.
- `qr_service.py` — thin qrcode wrapper. Reusable.

### 3. Clean dependency direction
- Dependencies flow downward: routers -> services -> models -> stdlib
- No circular imports anywhere in the codebase
- `relay/app/services/mount_registry.py` uses `TYPE_CHECKING` to avoid runtime tunnel import

### 4. Domain exception hierarchy
- Each package defines its own exceptions (`server/app/exceptions.py`, `relay/app/exceptions.py`, `agent/exceptions.py`, `tunnel/exceptions.py`)
- Typed, specific, with context fields — not generic `Exception`

### 5. Router organization
- Each router imports only the services it needs
- No cross-router dependencies
- Business logic mostly delegated to services

---

## Problems and Suggestions

### Problem 1: Empty `__init__.py` files — no declared public interfaces

**Where:** `server/__init__.py`, `server/app/services/__init__.py`, `relay/__init__.py`, `agent/__init__.py`

**Impact:** Consumers must know the internal module structure to import anything. There's no obvious "front door" for each package. Contrast with `tunnel/__init__.py` which does this perfectly.

**Suggestion:** Each package's `__init__.py` should re-export its public types and declare `__all__`. For example:
- `server/app/services/__init__.py` should expose service classes and their getter functions
- `agent/__init__.py` should expose `run_mount` and key utilities like `compute_backoff`, `parse_duration`
- `relay/__init__.py` should expose `create_relay_app` and `MountRegistry`

This is the single highest-leverage change for reusability — it makes each package self-describing.

---

### Problem 2: Agent directly imports server internals — can't be extracted standalone

**Where:**
- `agent/cli.py:13` — `from server.app.services.auth_service import hash_password`
- `agent/connection.py:24-26` — imports `ServerConfig`, `set_server_config`, `create_app`, `AuthTokenService`, `set_token_service` from server

**Impact:** The `agent/` package cannot be packaged or distributed independently. Installing the agent requires the entire server package.

**Why it exists:** The agent needs to (a) hash passwords and (b) spin up a local ASGI server to handle proxied requests from the relay.

**Suggestion:** Split into two changes:
1. **Extract `hash_password` / `verify_password` to a shared `crypto` module** (e.g., `shared/crypto.py` or a top-level `crypto.py`). Both server and agent import from there. These are pure bcrypt wrappers with no domain logic.
2. **The ASGI coupling is harder** — the agent legitimately needs to create a server app. This could be addressed by having the agent accept a factory callable (`Callable[[], ASGIApplication]`) rather than importing `create_app` directly. The glue layer in `server/app/cli.py` (which already orchestrates both) would pass the factory. This makes agent framework-agnostic — it just needs "something that speaks ASGI."

---

### Problem 3: Shared utilities trapped inside `agent/`

**Where:**
- `agent/backoff.py` — exponential backoff with jitter (stdlib only)
- `agent/duration.py` — duration string parsing like "30m", "2h" (stdlib only)
- `agent/display.py` — terminal output helpers (stdlib only)

**Impact:** `server/app/cli.py` already imports `agent.duration.parse_duration`. These are generic utilities that don't belong inside the agent package — they have zero agent-specific logic.

**Suggestion:** Move to a top-level `shared/` or `utils/` package. This makes the dependency direction honest: server and agent both depend on shared utilities, rather than server reaching into agent's internals.

---

### Problem 4: Global singleton pattern for dependency injection

**Where:** Every stateful service uses module-level `_instance` variables with `get_*()` / `set_*()`:
- `server/app/config.py` — `_config: ServerConfig | None`
- `server/app/services/auth_service.py` — `_token_service: AuthTokenService | None`
- `server/app/services/share_service.py` — `_share_service: ShareLinkService | None`
- `relay/app/services/mount_registry.py` — `_registry: MountRegistry | None`

**Impact:**
- Initialization order is implicit — call `set_*()` before `get_*()` or get a `RuntimeError`
- Makes it hard to run two server instances in one process (e.g., testing)
- Hides dependencies — a router's function signature doesn't reveal what services it needs

**Suggestion:** Consolidate initialization into an explicit bootstrap function per app. For example, a `server/app/bootstrap.py` that takes CLI args and returns all initialized services as a bundle. The app factory receives this bundle instead of reaching into global state. This doesn't require full DI framework — just explicit wiring in one place. FastAPI's `Depends()` could also be used for routers to declare their service dependencies.

---

### Problem 5: `connection_manager.py` stores raw FastAPI `WebSocket` objects

**Where:** `server/app/services/connection_manager.py:6` — `from fastapi import WebSocket`

**Impact:** This is the only service that has a framework import. It can't be tested without mocking FastAPI's WebSocket, and can't be reused with a different framework.

**Suggestion:** Define a minimal protocol/ABC (like `tunnel/protocol.py` does for `WebSocketProtocol`) that wraps the send/receive/close operations. The FastAPI router wraps the real WebSocket in this protocol before passing to the manager. The service stays framework-clean.

---

### Problem 6: Template path resolution via fragile relative paths

**Where:**
- `server/app/routers/share.py:30` — `Path(__file__).resolve().parent.parent.parent.parent / "templates"`
- Relay routers use similar patterns for `relay/templates/`

**Impact:** Four levels of `.parent` navigation is brittle. If any directory structure changes, templates break silently at runtime.

**Suggestion:** Define a `PROJECT_ROOT` constant in one place (e.g., `server/app/config.py` or a dedicated `paths.py`) and derive all template/static paths from it. Alternatively, use Python's `importlib.resources` for package-relative resource loading.

---

### Problem 7: Share service exceptions defined inside the service, not in `exceptions.py`

**Where:** `server/app/services/share_service.py` defines `ShareLinkExpiredError`, `ShareLinkRevokedError`, `ShareLinkNotFoundError` locally, while all other server exceptions live in `server/app/exceptions.py`.

**Impact:** Inconsistent. A consumer looking for server exception types has to know to check two places.

**Suggestion:** Move share-related exceptions to `server/app/exceptions.py` alongside `PathTraversalError`, `FileConflictError`, etc. Keep one canonical location for all domain exceptions per package.

---

### Problem 8: No logging configuration for server app

**Where:** `relay/app/logging.py` has `configure_logging()` with env-aware JSON/text formatting. The server app has no equivalent — it relies on uvicorn defaults.

**Impact:** Inconsistency between the two apps. The relay logging module is reusable, but there's no server-side equivalent.

**Suggestion:** Extract a shared logging module (or just reuse relay's `configure_logging` pattern) so both apps can configure structured logging consistently. The relay's `CloudJsonFormatter` pattern is particularly useful and should be shared.

---

### Problem 9: Client API endpoint paths are hardcoded and scattered

**Where:** `client/src/api/files.ts`, `shares.ts`, `clipboard.ts`, `fileRequests.ts` — each hardcodes endpoint paths like `/api/files`, `/api/shares`, etc.

**Impact:** No single source of truth for API routes. If an endpoint path changes, you need to update both the Python router and the TypeScript API client file.

**Suggestion:** Create a `client/src/api/endpoints.ts` constants file that centralizes all route paths. Each API module imports from there. This is a minor improvement but reduces the chance of path drift.

---

## Priority Order for Changes

| Priority | Problem | Effort | Impact on Reusability |
|----------|---------|--------|----------------------|
| 1 | Empty `__init__.py` files (Problem 1) | Low | High — makes packages self-describing |
| 2 | Shared utilities in agent (Problem 3) | Low | Medium — fixes incorrect dependency direction |
| 3 | Share exceptions location (Problem 7) | Low | Low — consistency fix |
| 4 | Agent imports server (Problem 2) | Medium | High — enables standalone agent package |
| 5 | Global singleton DI (Problem 4) | Medium | Medium — cleaner initialization, better testability |
| 6 | Template path resolution (Problem 6) | Low | Low — robustness fix |
| 7 | ConnectionManager framework coupling (Problem 5) | Medium | Medium — enables framework-agnostic WebSocket service |
| 8 | Shared logging (Problem 8) | Low | Low — consistency fix |
| 9 | Client endpoint constants (Problem 9) | Low | Low — minor DX improvement |

---

## Verification

After any modularity changes:
1. Run full test suite: `uv run pytest` — all existing tests must pass
2. Run ruff linter: `uv run ruff check .` — no import errors or unused imports
3. Verify each `__init__.py` that was modified still allows existing import patterns to work (no breaking changes)
4. For the agent extraction (Problem 2): verify `agent/` has no `from server.` imports except through the shared module
5. For the shared utilities (Problem 3): verify `server/app/cli.py` imports `parse_duration` from the new location
6. Manual test: `uv run network-file-server /tmp/test --port 8080` and `uv run network-file-server mount /tmp/test --server https://relay.example.com` both still work
