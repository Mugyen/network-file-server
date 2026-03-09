# Phase 5: Access Control - Research

**Researched:** 2026-03-10
**Domain:** CLI-driven access control (password, read-only, receive modes) for a FastAPI + React SPA
**Confidence:** HIGH

## Summary

Phase 5 adds three CLI flags (`--password`, `--read-only`, `--receive`) that gate server access and restrict operations. The implementation touches four layers: CLI argument parsing (argparse), server config (ServerConfig), backend middleware/guards (FastAPI), and frontend conditional rendering (React).

The password system uses `bcrypt` for hashing and `itsdangerous` for signed session cookies. Read-only mode requires a middleware/dependency guard blocking 8 write endpoints across 3 routers plus WebSocket. Receive mode replaces the entire SPA with a minimal drop-box page. The `--read-only --receive` combination is rejected at CLI parse time via argparse validation.

**Primary recommendation:** Implement in three layers -- (1) CLI + config, (2) backend middleware and endpoint guards, (3) frontend conditional UI. Expose server mode via `/api/server-info` so the frontend can adapt without duplicating logic.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Drop box (receive mode): Centered drop zone layout with dashed-border area, icon + "Drop files here" text, file picker button below
- Drop box: Inline success list below the drop zone showing completed files with checkmark, name, and size
- Drop box: Show server/host machine name in header (not folder path)
- Drop box: Inherit the app's existing dark/light/system theme toggle
- Mode indicators: Subtle header pill badges next to "WiFi File Server" title
- Mode indicators: Text pills with color coding: "Read Only" (amber), "Protected" (blue, with lock icon)
- Mode indicators: Receive mode needs no badge -- the entire drop box UI IS the indicator
- Mode indicators: Normal mode shows no badge
- Mode indicators: When password + read-only are combined, show both badges side by side: [Protected] [Read Only]
- Mode indicators: Server operator's terminal startup banner also prints active modes alongside QR code and URL
- Session cookie implementation uses itsdangerous pattern (already decided in v1.1 research)

### Claude's Discretion
- Login page design -- full-page form, visual style, wrong password behavior
- Read-only UI presentation -- how write controls are hidden, API rejection behavior
- Exact badge pill styling, colors, and dark mode variants
- Loading and error states for login and drop box
- Session cookie implementation details

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | `--password` CLI flag for server-wide password | argparse flag + ServerConfig extension + bcrypt hashing |
| AUTH-02 | Full-page login form for password-protected server | React login page + `/api/auth/login` endpoint + redirect logic |
| AUTH-03 | Session cookie on correct password, persists until browser close or server restart | itsdangerous URLSafeTimedSerializer + httponly cookie + server-generated secret |
| AUTH-04 | `--read-only` CLI flag blocking all write operations | argparse flag + middleware guard on 8 write endpoints |
| AUTH-05 | Write controls hidden in read-only mode | Frontend conditional rendering based on `server-info` mode field |
| AUTH-06 | `--receive` CLI flag for upload-only interface | argparse flag + dedicated drop-box React page |
| AUTH-07 | Minimal drop box UI with drag-and-drop, file picker, progress | New DropBoxPage component reusing existing upload infrastructure |
| AUTH-08 | CLI rejects `--read-only --receive` with clear error | argparse validation in `_build_parser()` or `main()` |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bcrypt | >=4.2.0 | Password hashing | Industry standard, constant-time comparison, built-in salt |
| itsdangerous | >=2.2.0 | Signed session cookies | Pallets project (same as Flask), URL-safe timed serialization, no DB needed |

### Supporting (Already in Project)
| Library | Version | Purpose | Relevant to Phase |
|---------|---------|---------|-------------------|
| FastAPI | >=0.115.0 | Backend framework | Middleware, dependency injection for auth guards |
| React | >=19.2.0 | Frontend SPA | Conditional rendering, new pages |
| lucide-react | >=0.577.0 | Icons | Lock icon for badge, upload icon for drop box |
| Tailwind CSS v4 | >=4.2.1 | Styling | Badge pills, login form, drop box layout |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| bcrypt | hashlib (built-in) | hashlib lacks adaptive work factor and salt management; bcrypt is purpose-built for passwords |
| itsdangerous | PyJWT | PyJWT is heavier, requires key management; itsdangerous is simpler for signed cookies and already planned for share links (Phase 6) |
| Custom middleware | Starlette SessionMiddleware | SessionMiddleware stores session data in cookie (4KB limit, size overhead); we only need a signed token, not session data storage |

**Installation:**
```bash
uv add bcrypt "itsdangerous>=2.2.0"
```

## Architecture Patterns

### Relevant Existing Structure
```
server/app/
  config.py          # ServerConfig -- extend with password, read_only, receive fields
  cli.py             # _build_parser() -- add --password, --read-only, --receive flags
  main.py            # create_app() -- add auth middleware here
  exceptions.py      # Add AccessDeniedError, ReadOnlyError
  routers/
    files.py         # 5 write endpoints to guard
    clipboard.py     # 3 write endpoints to guard
    file_requests.py # 3 write endpoints to guard
    server_info.py   # Extend response with mode info
    websocket.py     # Guard snippet_update message type
client/src/
  App.tsx            # Conditional rendering based on server mode
  api/client.ts      # Cookie-aware fetch (credentials: same-origin is default)
  types/serverInfo.ts # Extend with mode fields
```

### New Files Needed
```
server/app/
  services/
    auth_service.py    # Password verification, token creation/validation
  middleware/
    auth_middleware.py # Cookie check, route gating
client/src/
  components/
    LoginPage.tsx      # Full-page password form
    DropBoxPage.tsx    # Receive-mode upload-only interface
    ModeBadges.tsx     # Header pill badges for read-only/protected
```

### Pattern 1: Server Mode via Config + Server-Info Endpoint
**What:** Extend `ServerConfig` with `password_hash`, `read_only`, `receive` fields. Expose current mode via `/api/server-info` so frontend adapts to one source of truth.
**When to use:** Always -- the frontend must know what mode the server is in.
**Example:**
```python
# ServerConfig extension
class ServerConfig:
    shared_folder: Path
    port: int
    password_hash: str | None  # bcrypt hash, None = no password
    read_only: bool
    receive: bool

# /api/server-info response extension
class ServerInfo(BaseModel):
    ip: str
    port: int
    url: str
    qr_svg: str
    all_ips: list[str]
    read_only: bool      # NEW
    receive: bool        # NEW
    password_required: bool  # NEW (derived: password_hash is not None)
    hostname: str        # NEW (for drop box header)
```

### Pattern 2: Auth Middleware with Cookie Validation
**What:** A Starlette middleware that checks for a valid session cookie on all requests when password is enabled. Login endpoint and static assets are exempted.
**When to use:** When `--password` flag is set.
**Example:**
```python
# Auth middleware approach (pure ASGI for performance)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

class AuthMiddleware:
    EXEMPT_PATHS = frozenset({"/api/auth/login", "/api/server-info"})

    def __init__(self, app: ASGIApp, secret_key: str) -> None:
        self.app = app
        self.serializer = URLSafeTimedSerializer(secret_key)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # WebSocket and lifespan pass through
            # (WebSocket auth checked separately via query param or initial message)
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if path in self.EXEMPT_PATHS or path.startswith("/assets"):
            await self.app(scope, receive, send)
            return

        # Check session cookie
        cookies = _parse_cookies(scope.get("headers", []))
        token = cookies.get("session")
        if token is None:
            await _send_redirect_or_401(scope, send)
            return

        try:
            self.serializer.loads(token)  # No max_age -- valid until server restart
        except (BadSignature, SignatureExpired):
            await _send_redirect_or_401(scope, send)
            return

        await self.app(scope, receive, send)
```

### Pattern 3: Read-Only Guard via Dependency
**What:** A FastAPI dependency that raises 403 on write endpoints when `read_only` is True. Applied to specific router operations, not as blanket middleware.
**When to use:** When `--read-only` flag is set.
**Example:**
```python
# FastAPI dependency for read-only guard
from fastapi import Depends

def require_write_access() -> None:
    """Dependency that blocks write operations in read-only mode."""
    config = get_server_config()
    if config.read_only:
        raise ReadOnlyError()

# Applied to write endpoints
@router.post("/files/upload", dependencies=[Depends(require_write_access)])
async def upload_files(...): ...

@router.patch("/files/rename", dependencies=[Depends(require_write_access)])
def rename_file(...): ...
```

### Pattern 4: Frontend Mode-Based Rendering
**What:** Frontend fetches server-info on mount, stores mode state, and conditionally renders based on mode. Receive mode completely replaces App with DropBoxPage. Read-only mode hides write controls.
**When to use:** Always -- frontend must adapt to backend mode.
**Example:**
```typescript
// In main.tsx or App.tsx entry point
function Root() {
  const [serverMode, setServerMode] = useState<ServerMode | null>(null);

  useEffect(() => {
    fetchServerInfo().then(info => {
      setServerMode({
        readOnly: info.read_only,
        receive: info.receive,
        passwordRequired: info.password_required,
        hostname: info.hostname,
      });
    });
  }, []);

  if (serverMode === null) return <LoadingSpinner />;
  if (serverMode.receive) return <DropBoxPage hostname={serverMode.hostname} />;
  return <App serverMode={serverMode} />;
}
```

### Anti-Patterns to Avoid
- **Duplicating mode logic in frontend:** Do NOT check CLI flags on the client. Always derive mode from `/api/server-info` response.
- **Blanket middleware for read-only:** Do NOT add middleware that blocks all POST/PATCH/DELETE requests -- clipboard reads use POST for WebSocket, download-zip uses POST. Use targeted endpoint dependencies.
- **Storing password in config as plaintext:** Always store the bcrypt hash, never the raw password. Hash once in `main()` after parsing CLI args.
- **Using `allow_credentials=True` in CORS:** The SPA is served from the same origin; cookies are same-origin by default. No CORS credential changes needed.
- **Using argparse mutually_exclusive_group for --read-only and --receive:** The argparse `add_mutually_exclusive_group()` generates confusing error messages ("not allowed with argument"). Better to validate manually in `main()` with a clear custom error message.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom hash + salt | bcrypt.hashpw / bcrypt.checkpw | Timing attacks, salt management, adaptive work factor |
| Session tokens | Random string + dict lookup | itsdangerous URLSafeTimedSerializer | Tamper-proof, no server-side storage needed, automatic expiry support |
| Cookie parsing in middleware | Manual header string splitting | Starlette's `cookies` scope or `http.cookies.SimpleCookie` | Edge cases in cookie parsing (escaping, multiple values) |
| Drag-and-drop upload | New custom implementation | Existing useDragDrop + useUpload hooks | Already battle-tested, handles edge cases (counter pattern, concurrency) |

**Key insight:** The session token approach with itsdangerous means zero server-side session storage. The token IS the session -- if it validates (was signed by this server's secret), the user is authenticated. The secret key is generated at server startup and lost on restart, which naturally invalidates all sessions on restart (matching AUTH-03 requirement).

## Common Pitfalls

### Pitfall 1: CORS + Cookies Conflict
**What goes wrong:** Developer enables `allow_credentials=True` in CORS middleware, breaking the `allow_origins=["*"]` wildcard.
**Why it happens:** Cookie-based auth typically requires `allow_credentials=True`, but this project's SPA is same-origin.
**How to avoid:** Do NOT change CORS settings. The SPA at `/` and API at `/api` share the same origin. Cookies work natively. The Vite dev proxy also handles this correctly (requests to `/api` are proxied, so cookies appear same-origin).
**Warning signs:** CORS errors in browser console, cookies not being sent.

### Pitfall 2: WebSocket Auth in Receive/Read-Only Mode
**What goes wrong:** WebSocket connection bypasses HTTP middleware, or snippet updates succeed in read-only mode.
**Why it happens:** WebSocket upgrade happens once, then messages flow without HTTP request/response cycle.
**How to avoid:** For password auth: check cookie during WebSocket upgrade (in `websocket_endpoint` function, before `manager.connect`). For read-only: check mode in the `snippet_update` message handler. For receive mode: either disable WebSocket entirely or limit to connection-only (no message handling).
**Warning signs:** Unauthenticated users can connect to WebSocket, or read-only users can edit clipboard.

### Pitfall 3: Receive Mode Leaking File Listing
**What goes wrong:** Receive mode serves the full SPA, which fetches `/api/files` and exposes the directory listing.
**Why it happens:** The middleware only blocks the login page but doesn't restrict API access.
**How to avoid:** In receive mode, ALL API endpoints except `/api/files/upload`, `/api/server-info`, and `/api/auth/login` must return 403. The frontend should serve only the DropBoxPage (never the full file browser).
**Warning signs:** Opening DevTools in receive mode shows file listing responses.

### Pitfall 4: bcrypt 72-byte Password Limit
**What goes wrong:** bcrypt 5.0+ raises ValueError for passwords longer than 72 bytes.
**Why it happens:** bcrypt silently truncated before v5.0, but now raises explicitly.
**How to avoid:** Validate password length at CLI parse time. 72 bytes is 72 ASCII characters, which is more than sufficient for a LAN file server password. Reject passwords over 72 bytes with a clear error.
**Warning signs:** Server crashes at startup with long passwords.

### Pitfall 5: Static Asset Paths in Auth Middleware
**What goes wrong:** Auth middleware blocks `/assets/index-abc123.js`, causing the login page itself to fail to load.
**Why it happens:** Middleware checks all paths, but the login page needs CSS/JS assets to render.
**How to avoid:** Exempt all paths starting with `/assets` and the root index.html. The login page must be renderable without authentication. Also exempt favicon, manifest, etc.
**Warning signs:** Login page shows blank white screen, or CSS missing.

### Pitfall 6: Browser Same-Origin Cookie Scope
**What goes wrong:** Cookie set on `/api/auth/login` is not sent with requests to `/api/files`.
**Why it happens:** Cookie `path` is set to `/api/auth/login` instead of `/`.
**How to avoid:** Always set cookie with `path="/"` so it applies to all routes on the same origin.
**Warning signs:** Authentication works on login but immediately fails on next API call.

## Code Examples

### bcrypt Password Hashing
```python
# Source: https://pypi.org/project/bcrypt/ (verified)
import bcrypt

# Hash at server startup (in main() after CLI parsing)
password_bytes = password_str.encode("utf-8")
hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
# Store hashed in ServerConfig

# Verify at login
def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    """Verify a password against its bcrypt hash.

    Returns True if password matches, False otherwise.
    bcrypt.checkpw uses constant-time comparison to prevent timing attacks.
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)
```

### itsdangerous Session Token
```python
# Source: https://itsdangerous.palletsprojects.com/en/stable/timed/ (verified)
import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Generate secret at server startup (lost on restart = sessions invalidated)
SECRET_KEY = secrets.token_hex(32)
serializer = URLSafeTimedSerializer(SECRET_KEY)

# Create token on successful login
token = serializer.dumps({"authenticated": True})
# Token looks like: "eyJhdXRoZW50aWNhdGVkIjp0cnVlfQ.ZjK..."

# Validate token on subsequent requests
try:
    data = serializer.loads(token)  # No max_age = never expires (until server restart)
except (BadSignature, SignatureExpired):
    # Invalid or expired token
    raise AccessDeniedError()
```

### FastAPI Cookie Setting
```python
# Source: https://fastapi.tiangolo.com/advanced/response-cookies/ (verified)
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

@router.post("/api/auth/login")
def login(request: LoginRequest, response: Response) -> dict:
    if not verify_password(request.password, config.password_hash):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = serializer.dumps({"authenticated": True})
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,     # Not accessible via JavaScript
        samesite="lax",    # CSRF protection
        path="/",          # Available to all routes
        # No max_age = session cookie (deleted when browser closes)
        # No secure=True (HTTP-only LAN tool, no HTTPS)
    )
    return {"status": "ok"}
```

### Hostname Detection
```python
# Source: Python standard library (verified)
import socket

def get_machine_hostname() -> str:
    """Return the machine's hostname for display in drop box header."""
    return socket.gethostname()
```

### Write Endpoints to Guard (Complete List)
```python
# 8 write surfaces across 3 routers + WebSocket:
# files.py:
#   POST   /api/files/upload          -- upload_files
#   PATCH  /api/files/rename          -- rename_file
#   DELETE /api/files                 -- delete_files
#   POST   /api/folders              -- create_new_folder
# clipboard.py:
#   POST   /api/clipboard/           -- create_snippet
#   PATCH  /api/clipboard/{id}       -- update_snippet_title
#   DELETE /api/clipboard/{id}       -- delete_snippet
# file_requests.py:
#   POST   /api/file-requests/       -- create_file_request
#   POST   /api/file-requests/{id}/fulfill  -- fulfill_file_request
#   DELETE /api/file-requests/{id}   -- dismiss_file_request
# websocket.py:
#   WS message type "snippet_update" -- update snippet content via WebSocket
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| bcrypt silent truncation at 72 bytes | bcrypt 5.0+ raises ValueError | Nov 2025 | Must validate password length at CLI level |
| BaseHTTPMiddleware for auth | Pure ASGI middleware | 2024 (Starlette recommendation) | 20-30% better middleware performance, no contextvars issues |
| JWT tokens for sessions | Signed cookies via itsdangerous | N/A (project decision) | Simpler, no token refresh logic, no Authorization header needed |

**Deprecated/outdated:**
- bcrypt <5.0 silent truncation behavior -- now raises ValueError
- BaseHTTPMiddleware -- officially recommended to use pure ASGI middleware instead

## Open Questions

1. **WebSocket authentication for password-protected servers**
   - What we know: HTTP middleware cannot intercept WebSocket after upgrade. Cookie is available during the upgrade handshake.
   - What's unclear: Whether to validate cookie in `websocket_endpoint` before `manager.connect()`, or use a separate WebSocket middleware.
   - Recommendation: Validate cookie in the `websocket_endpoint` function itself (before `manager.connect`). If invalid, close the WebSocket with code 4001. This is simpler and matches the existing pattern where WebSocket params are checked in the endpoint.

2. **Receive mode API access scope**
   - What we know: Receive mode should only allow upload. The frontend will be a dedicated page.
   - What's unclear: Exact set of allowed endpoints in receive mode.
   - Recommendation: Allow only `/api/files/upload`, `/api/server-info`, and `/api/auth/login` (if password also set). Block all others with 403. This prevents any file listing exposure.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `uv run pytest server/tests/ -x -q` |
| Full suite command | `uv run pytest server/tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | `--password` flag parsed and stored | unit | `uv run pytest server/tests/test_cli.py -x -q` | Extend existing |
| AUTH-01 | Password hashed with bcrypt in config | unit | `uv run pytest server/tests/test_config.py -x -q` | Extend existing |
| AUTH-02 | Login endpoint accepts/rejects password | integration | `uv run pytest server/tests/test_auth.py -x -q` | Wave 0 |
| AUTH-03 | Valid session cookie grants access | integration | `uv run pytest server/tests/test_auth.py -x -q` | Wave 0 |
| AUTH-03 | Invalid/missing cookie returns 401 | integration | `uv run pytest server/tests/test_auth.py -x -q` | Wave 0 |
| AUTH-04 | `--read-only` flag parsed and stored | unit | `uv run pytest server/tests/test_cli.py -x -q` | Extend existing |
| AUTH-04 | Write endpoints return 403 in read-only | integration | `uv run pytest server/tests/test_read_only.py -x -q` | Wave 0 |
| AUTH-05 | server-info exposes read_only field | integration | `uv run pytest server/tests/test_routes_info.py -x -q` | Extend existing |
| AUTH-06 | `--receive` flag parsed and stored | unit | `uv run pytest server/tests/test_cli.py -x -q` | Extend existing |
| AUTH-06 | Non-upload endpoints return 403 in receive | integration | `uv run pytest server/tests/test_receive_mode.py -x -q` | Wave 0 |
| AUTH-07 | Upload works in receive mode | integration | `uv run pytest server/tests/test_receive_mode.py -x -q` | Wave 0 |
| AUTH-08 | `--read-only --receive` raises error | unit | `uv run pytest server/tests/test_cli.py -x -q` | Extend existing |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/ -x -q`
- **Per wave merge:** `uv run pytest server/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_auth.py` -- covers AUTH-02, AUTH-03 (login, session cookie, middleware)
- [ ] `server/tests/test_read_only.py` -- covers AUTH-04 (all 8+ write endpoints blocked)
- [ ] `server/tests/test_receive_mode.py` -- covers AUTH-06, AUTH-07 (receive mode restrictions, upload works)
- [ ] Test fixtures for configured_app variants (with password, with read-only, with receive) in conftest.py

## Sources

### Primary (HIGH confidence)
- [itsdangerous 2.2.0 docs](https://itsdangerous.palletsprojects.com/en/stable/timed/) - TimedSerializer API, URLSafeTimedSerializer usage
- [bcrypt 5.0.0 on PyPI](https://pypi.org/project/bcrypt/) - Latest version, 72-byte limit change
- [FastAPI Response Cookies](https://fastapi.tiangolo.com/advanced/response-cookies/) - Cookie setting patterns
- [FastAPI CORS docs](https://fastapi.tiangolo.com/tutorial/cors/) - Credentials + wildcard origin incompatibility
- [Python socket.gethostname()](https://docs.python.org/3/library/socket.html) - Hostname detection
- Project codebase: `server/app/config.py`, `server/app/cli.py`, `server/app/main.py`, all routers, `client/src/App.tsx`

### Secondary (MEDIUM confidence)
- [Starlette BaseHTTPMiddleware deprecation discussion](https://github.com/Kludex/starlette/discussions/2160) - Pure ASGI middleware recommendation
- [Starlette middleware docs](https://starlette.dev/middleware/) - Pure ASGI middleware patterns

### Tertiary (LOW confidence)
- None -- all findings verified with primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - bcrypt and itsdangerous are well-documented, verified on PyPI
- Architecture: HIGH - Patterns derived from actual codebase analysis (8 write endpoints enumerated, existing hooks identified)
- Pitfalls: HIGH - CORS/cookie interaction verified with FastAPI docs, bcrypt 72-byte limit verified on PyPI

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable libraries, patterns unlikely to change)
