# Technology Stack -- v1.1 Additions

**Project:** WiFi File Server v1.1 (Share & Access Control)
**Researched:** 2026-03-10
**Scope:** NEW dependencies only. Existing stack (React 19, Tailwind v4, FastAPI, uvicorn, Pydantic, WebSocket, qrcode, aiofiles, zipstream-ng, ifaddr, python-multipart) is validated and NOT re-researched.

## Feature-to-Dependency Map

| Feature | New Backend Deps | New Frontend Deps | Stdlib Only? |
|---------|-----------------|-------------------|--------------|
| Password protection | bcrypt | none | No |
| Read-only mode | none | none | YES |
| Receive mode / dropbox | none | none | YES |
| Expiring share links | itsdangerous | none | No |
| Device discovery | zeroconf | none | No |
| Terminal UI | rich | none | No |
| Speed test | none | none | YES |

**Summary: 4 new Python dependencies, 0 new frontend dependencies.**

## New Backend Dependencies

### 1. bcrypt -- Password Hashing (for Password Protection)

| Attribute | Value |
|-----------|-------|
| Package | `bcrypt` |
| Version | `>=4.2.0` |
| Purpose | Hash and verify the `--password` CLI argument for server-wide access gating |
| Confidence | HIGH |

**Why bcrypt (not passlib, not stdlib hashlib):**
- `passlib` is unmaintained since 2020 and throws deprecation warnings on Python 3.13+. FastAPI's own docs have migrated away from it. Do NOT use passlib.
- `hashlib` provides raw hash algorithms (SHA256, etc.) but no work-factor-based password hashing. Rolling your own password scheme with hashlib is a security mistake.
- `bcrypt` is the actively maintained standard (v4.2.1 is latest stable as of early 2026, v5.0.0 is available but introduces a breaking change where passwords >72 bytes raise ValueError -- stick with 4.x for now since LAN passwords are short). It provides `bcrypt.hashpw()` and `bcrypt.checkpw()` directly with no wrapper library needed.

**Integration point:** The `--password` CLI flag value gets hashed once at startup with `bcrypt.hashpw()`. On every request, FastAPI middleware calls `bcrypt.checkpw()` against a token from the `Authorization` header or a session cookie. Since this is a LAN tool with low request rates, bcrypt's intentional slowness is irrelevant to performance.

**Why NOT token-based auth (JWT):** This is a single shared password for LAN access, not multi-user auth. A password check on each request (or a simple session cookie after first auth) is far simpler than JWT token issuance/refresh. JWT is over-engineering for "enter the password to use the server."

### 2. itsdangerous -- Expiring Share Link Tokens

| Attribute | Value |
|-----------|-------|
| Package | `itsdangerous` |
| Version | `>=2.2.0` |
| Purpose | Generate URL-safe, time-stamped, signed tokens for expiring share links |
| Confidence | HIGH |

**Why itsdangerous (not PyJWT, not stdlib):**
- `itsdangerous` is purpose-built for exactly this use case: sign data (file path + expiration) into a URL-safe token, then verify + expire it later. Its `URLSafeTimedSerializer` produces compact tokens that can go directly into URLs.
- `PyJWT` is designed for authorization tokens with claims/audiences -- overkill for "share this file for 1 hour." JWT tokens are also longer and uglier in URLs.
- Rolling your own with `hmac` + `time` is fragile and lacks the `max_age` expiry validation that itsdangerous provides out of the box.
- itsdangerous 2.2.0 is stable (released April 2024, from the Pallets project -- same maintainers as Flask/Werkzeug).

**Integration point:** A new endpoint `POST /api/share-link` takes a file path and TTL (seconds), serializes them with `URLSafeTimedSerializer(app_secret_key)`, returns the token. A `GET /api/shared/{token}` endpoint deserializes with `max_age=ttl`, validates, and serves the file. The secret key can be auto-generated per server session (using `secrets.token_hex(32)` from stdlib) since share links only need to survive the current server run.

### 3. zeroconf -- mDNS Device Discovery

| Attribute | Value |
|-----------|-------|
| Package | `zeroconf` |
| Version | `>=0.146.0` |
| Purpose | Register the server as an mDNS service on the LAN so other instances can discover each other |
| Confidence | HIGH |

**Why zeroconf (not manual broadcast, not SSDP):**
- `zeroconf` (python-zeroconf) is the de facto Python implementation of mDNS/DNS-SD (the same protocol that powers Apple Bonjour and Linux Avahi). Actively maintained with recent releases (0.148.0, October 2025), supports Python 3.11+, async-native.
- Manual UDP broadcast requires writing your own protocol, handling packet parsing, TTL, announcement intervals, and cross-platform multicast group joining. zeroconf handles all of this.
- SSDP (UPnP) is heavier, more complex, and less universally supported than mDNS for service discovery.

**Integration point:** On server start, register a service like `_wifi-file-server._tcp.local.` with the server's IP, port, and shared folder name as TXT record properties. On the client side (or a separate CLI command), use `ServiceBrowser` to discover running servers on the LAN. The registration should be cleaned up on server shutdown. The existing `ifaddr` dependency already provides the network interfaces that zeroconf needs.

**Important:** zeroconf uses asyncio internally and integrates cleanly with FastAPI's event loop. Register the service in a `lifespan` context manager on the FastAPI app so cleanup happens automatically on shutdown.

### 4. rich -- Terminal UI Dashboard

| Attribute | Value |
|-----------|-------|
| Package | `rich` |
| Version | `>=13.9.0` |
| Purpose | Rich terminal dashboard showing live server stats, connected devices, transfer activity |
| Confidence | HIGH |

**Why rich (not Textual, not curses, not blessed):**
- `rich` provides `Live` display, `Table`, `Panel`, `Layout`, `Progress`, and `Console` -- everything needed for a live-updating terminal dashboard. It works within a standard terminal (no TUI app framework needed).
- `Textual` (by the same author) is a full TUI application framework with widgets, focus management, and CSS-like styling. It is far too heavy for "show server stats in the terminal." Textual replaces your entire terminal with an interactive app -- we just want a dashboard below the server output.
- `curses` (stdlib) is low-level, platform-inconsistent (poor Windows support), and requires manual character-by-character rendering.
- `blessed` is a curses wrapper with better API but still lower-level than rich.
- rich 13.9.0+ is stable (14.x releases available; 13.9+ is the minimum for `Live` display with `Layout` support). Latest is 14.1.0 (released early 2026).

**Integration point:** Replace the current `print()` statements in `cli.py` with rich `Console` output. The live dashboard uses `rich.live.Live` with a `Layout` containing panels for: server URL + QR code, connected devices (from `ConnectionManager.device_names`), recent transfers, and upload/download activity. The `Live` display updates on a periodic interval (every 1-2 seconds) by reading state from the existing `ConnectionManager` singleton.

**Important caveat:** rich's `Live` display and uvicorn's log output will fight for the terminal. Solution: either (a) redirect uvicorn's access logs to a file when terminal UI is active, or (b) capture uvicorn logs and display them in a rich `Panel`. The CLI should support a `--no-tui` flag to disable the terminal UI and fall back to plain text output.

## Dependencies NOT Needed (Anti-Recommendations)

These are libraries you might think are needed but are NOT. Do not add them.

| Library | Why You Might Think It's Needed | Why It's NOT |
|---------|--------------------------------|-------------|
| `passlib` | FastAPI security tutorials reference it | Unmaintained since 2020. Breaks on Python 3.13+. Use `bcrypt` directly. |
| `python-jose` / `PyJWT` | Token generation for share links | itsdangerous is simpler and purpose-built for URL tokens. JWT is for multi-user auth, not file sharing links. |
| `fastapi-users` | Password/auth management | Massive auth framework with DB models, email verification, OAuth. We need one shared password, not user management. |
| `Textual` | Terminal UI | Full TUI framework that takes over the terminal. rich's `Live` display is sufficient and non-invasive. |
| `speedtest-cli` | Speed test | Tests internet speed via speedtest.net servers. We need LAN speed between the server and a connected client browser, which is a custom endpoint. |
| `netifaces` | Network interface detection | Abandoned (last release 2021). The project already uses `ifaddr` which serves the same purpose and is actively maintained. |
| `flask-limiter` / `slowapi` | Rate limiting for password attempts | On a LAN tool with a single password, brute force is not a realistic threat model. Adding rate limiting infrastructure is over-engineering. |
| `cryptography` | Encryption for tokens | itsdangerous uses HMAC-SHA512 internally. The `cryptography` library is a heavy C dependency that's unnecessary here. |

## Features Requiring NO New Dependencies

### Read-Only Mode
Uses FastAPI middleware that checks `request.method` against an allow-list. When `--read-only` is set in `ServerConfig`, the middleware returns `403 Forbidden` for POST, PUT, PATCH, DELETE requests on `/api/files/*` endpoints. Implementation is ~20 lines of middleware code. The frontend receives a `read_only: true` flag from `/api/server-info` and hides upload/delete/rename UI.

**Implementation pattern:** FastAPI middleware (not dependency injection) because this is a blanket server-wide policy, not a per-route concern. Middleware runs before routing and can reject the request early.

### Receive Mode / Dropbox
Inverse of read-only: a mode where clients can ONLY upload, not browse or download. Same middleware pattern as read-only but with different allowed methods/paths. The "dropbox" URL is a separate frontend view (e.g., `/dropbox`) that shows only an upload form. Backend filters: allow POST to `/api/files/upload`, block GET on `/api/files`, `/api/files/download`, `/api/files/preview`.

**No new dependencies.** The same `ServerConfig` holds a `server_mode` enum (`FULL`, `READ_ONLY`, `RECEIVE_ONLY`) and the middleware enforces it.

### Speed Test
A custom endpoint `GET /api/speed-test/download` that streams a chunk of random bytes (configurable size, default 10MB) to the client. The client times how long the download takes and calculates throughput. An optional `POST /api/speed-test/upload` endpoint accepts a blob and measures upload speed.

**No new dependencies.** Uses `os.urandom()` for random bytes and `StreamingResponse` (already imported from FastAPI). The client uses the existing XHR pattern (from `useUpload.ts`) to track progress and timing. Total implementation: ~30 lines backend, ~50 lines frontend.

## Updated pyproject.toml Dependencies

```toml
[project]
dependencies = [
    # Existing (unchanged)
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "pydantic>=2.10.0",
    "python-multipart>=0.0.20",
    "aiofiles>=24.1.0",
    "qrcode>=8.0",
    "ifaddr>=0.2.0",
    "zipstream-ng>=1.9.0",
    # NEW for v1.1
    "bcrypt>=4.2.0",           # Password protection
    "itsdangerous>=2.2.0",     # Expiring share links
    "zeroconf>=0.146.0",       # mDNS device discovery
    "rich>=13.9.0",            # Terminal UI dashboard
]
```

```bash
# Install new v1.1 dependencies
uv add "bcrypt>=4.2.0" "itsdangerous>=2.2.0" "zeroconf>=0.146.0" "rich>=13.9.0"
```

No new frontend dependencies. The frontend changes are pure React/TypeScript using existing patterns.

## Integration Points with Existing Code

### ServerConfig (server/app/config.py)
Needs new fields:
- `password_hash: bytes | None` -- bcrypt hash of `--password` value (None = no password)
- `server_mode: ServerMode` -- enum: `FULL`, `READ_ONLY`, `RECEIVE_ONLY`
- `tui_enabled: bool` -- whether to show rich terminal UI

### CLI (server/app/cli.py)
New argparse flags:
- `--password` -- string, hashed with bcrypt at startup
- `--read-only` -- boolean flag, sets `server_mode` to `READ_ONLY`
- `--receive-only` -- boolean flag, sets `server_mode` to `RECEIVE_ONLY`
- `--no-tui` -- boolean flag, disables rich terminal UI

### Middleware (NEW: server/app/middleware.py)
Two middleware classes:
1. `PasswordAuthMiddleware` -- checks `Authorization` header or `X-Auth-Token` cookie
2. `AccessModeMiddleware` -- enforces read-only or receive-only restrictions based on `ServerConfig.server_mode`

### FastAPI App (server/app/main.py)
- Add middleware in `create_app()`
- Add `lifespan` context manager for zeroconf service registration/cleanup
- Add new routers: `share_links`, `speed_test`

### Server Info (server/app/routers/server_info.py)
Extend `ServerInfo` schema to include:
- `requires_password: bool` -- tells frontend to show login prompt
- `server_mode: str` -- tells frontend what UI to render
- `server_name: str` -- human-readable name for mDNS discovery

### ConnectionManager (server/app/services/connection_manager.py)
Already tracks device_id, device_name, and active connections. For the "device discovery" feature, the existing `device_names` dict and `device_count()` method provide everything needed. The terminal UI reads from this singleton to show connected devices.

## Alternatives Considered (v1.1 specific)

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Password hashing | bcrypt | passlib[bcrypt] | passlib is unmaintained, throws deprecation warnings on Python 3.13+ |
| Password hashing | bcrypt | argon2-cffi | Argon2 is technically superior but requires a C compiler for cffi. bcrypt has pre-built wheels and is simpler for a single shared password use case |
| Share link tokens | itsdangerous | PyJWT | JWT tokens are verbose for URLs and designed for multi-user auth claims. itsdangerous produces shorter, URL-safe tokens |
| Share link tokens | itsdangerous | stdlib hmac + time | Rolling your own requires handling serialization, timestamp encoding, constant-time comparison, and expiry checks. itsdangerous does all of this correctly |
| Service discovery | zeroconf | Manual UDP broadcast | Writing custom multicast UDP is error-prone and requires handling cross-platform network interface differences. zeroconf abstracts this |
| Terminal UI | rich | Textual | Textual takes over the entire terminal as a TUI app. We want a dashboard that coexists with server logs, not replaces them |
| Terminal UI | rich | click + colorama | Click provides colored output but no live-updating layouts, tables, or progress bars. Rich is strictly more capable |
| Speed test | Custom endpoint | speedtest-cli | speedtest-cli measures internet speed via external servers. We need to measure LAN throughput between the server and the browser client |

## Sources

- [FastAPI Security documentation](https://fastapi.tiangolo.com/tutorial/security/) -- password auth patterns
- [FastAPI middleware documentation](https://fastapi.tiangolo.com/tutorial/middleware/) -- HTTP method filtering pattern
- [bcrypt PyPI](https://pypi.org/project/bcrypt/) -- v4.2.x/5.0.0 latest releases
- [itsdangerous documentation](https://itsdangerous.palletsprojects.com/en/stable/timed/) -- URLSafeTimedSerializer, max_age expiry
- [itsdangerous PyPI](https://pypi.org/project/itsdangerous/) -- v2.2.0 (latest stable, April 2024)
- [python-zeroconf GitHub](https://github.com/python-zeroconf/python-zeroconf) -- async mDNS, ServiceBrowser
- [zeroconf PyPI](https://pypi.org/project/zeroconf/) -- v0.148.0 (latest, October 2025)
- [Rich documentation](https://rich.readthedocs.io/en/latest/live.html) -- Live display, Layout
- [Rich PyPI](https://pypi.org/project/rich/) -- v14.1.0 (latest stable)
- [FastAPI dependency injection vs middleware discussion](https://github.com/fastapi/fastapi/discussions/8867) -- pattern selection rationale
- [passlib maintenance concern](https://github.com/fastapi/fastapi/discussions/11773) -- FastAPI community migration away from passlib
- [Building Rich terminal dashboards](https://www.willmcgugan.com/blog/tech/post/building-rich-terminal-dashboards/) -- Live + Layout patterns
