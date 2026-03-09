# Feature Research: v1.1 Share & Access Control

**Domain:** LAN file sharing web application -- access control, sharing modes, server UX
**Researched:** 2026-03-10
**Confidence:** HIGH (verified against existing codebase, competitor implementations, and official documentation)
**Scope:** v1.1 features ONLY. v1.0 features (file CRUD, preview, clipboard, file requests, WebSocket, QR, drag-drop, batch ops) are shipped and validated.

## Context

v1.0 shipped with file management, preview, real-time sync (WebSocket toasts, clipboard, file requests), QR code connect, and dark mode. v1.1 adds access control, sharing modes, and server-side UX. The codebase has ~9,600 LOC across FastAPI + React + WebSocket infrastructure.

Existing infrastructure that v1.1 features build on:
- **CLI** (`server/app/cli.py`): argparse with `folder`, `--port`, `--host` flags
- **Config** (`server/app/config.py`): `ServerConfig(shared_folder, port)` with global get/set
- **WebSocket** (`server/app/services/connection_manager.py`): `ConnectionManager` with device tracking (device_id, device_name), broadcast, send_to, device_count
- **API client** (`client/src/api/client.ts`): `apiFetch`, `apiPost`, `apiPatch`, `apiDelete`, `uploadWithProgress`
- **Persistence** (`server/app/services/persistence.py`): atomic JSON read/write for clipboard and file requests
- **Server info endpoint** (`/api/server-info`): already returns server metadata to frontend
- **Enums** (`server/app/models/enums.py`): `WSMessageType`, `ToastType`, `ConflictResolution`, `RequestStatus`

---

## Feature Landscape

### Table Stakes (Users Expect These)

For a file sharing tool that claims access control, these are non-negotiable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Password protection** | Any tool claiming "access control" must have a password gate. Windows file sharing, uploadserver (PyPI), FileBrowser -- all support it. Without this, sharing on hotel/cafe WiFi is a non-starter. | LOW | Server-wide password via `--password` CLI flag. FastAPI middleware checks every request. Single shared password, not per-user accounts. |
| **Read-only mode** | Standard access level in every file sharing tool. "I want to share files but not let anyone modify my folder." Windows shares, FTP, FileBrowser all have this. | LOW | `--read-only` CLI flag. Block POST/PATCH/DELETE at middleware level. Hide upload/delete/rename UI elements. |
| **Password entry UI** | The password gate needs a frontend form. Without it, users get raw 401 errors. | LOW | Full-page login form with password input, submit button, error state. Store auth token in cookie or localStorage. |

### Differentiators (Competitive Advantage)

Features that elevate this tool above PairDrop, LocalSend, and basic `python -m http.server`.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Receive mode / digital drop box** | Upload-only interface for collecting files. "Upload your homework here" or "Drop your event photos." EZ File Drop is a paid service for this. No open-source LAN tool offers it. Distinct from read-only (which shows files but blocks writes) -- drop box blocks browsing and only allows uploads. | MEDIUM | Separate minimal UI showing only an upload form. Activated via `--receive` CLI flag. Hides file listing, search, preview, clipboard entirely. |
| **Expiring share links** | Generate a temporary URL for a specific file that auto-expires. "Here's the deck, link dies in 1 hour." No open-source LAN tool has built-in expiring links. | MEDIUM-HIGH | Server generates cryptographically random token mapped to file path + expiry. In-memory dict storage. Client UI: "Share" button generates link with configurable TTL. |
| **Device discovery panel** | Expand the existing connection status dot into a panel showing device names, connection times, and IP addresses. PairDrop does this well with its device circle UI. Makes the tool feel social. | LOW-MEDIUM | ConnectionManager already tracks device_id and device_name. Add IP + timestamp. New API endpoint + React panel. |
| **Rich terminal UI** | Replace plain `print()` startup output with a Rich-powered live dashboard showing connected devices, transfer activity, QR code, and server stats. No LAN file sharing CLI does this. | MEDIUM-HIGH | Rich library's `Live` display. Must coexist with uvicorn via `uvicorn.Server.serve()` in asyncio task. |
| **Network speed test** | Built-in LAN speed measurement between server and client. OpenSpeedTest proves this works with pure XHR. Useful for diagnosing transfer speed issues. | MEDIUM | Server endpoints for upload/download speed measurement. Client-side XHR with progress tracking (pattern already exists). |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Per-user accounts / multi-password** | "Different passwords for different people." | Adds user management complexity (storage, sessions, CRUD UI). Turns a simple LAN tool into a mini IAM system. Contradicts "zero setup" core value. | Single shared password is sufficient. If per-user access is needed, that is a v2 feature. |
| **HTTPS / TLS for password protection** | "Passwords over HTTP are insecure." | Adding TLS requires certificate management (self-signed = browser warnings, Let's Encrypt = domain needed). Massive friction increase for a LAN tool. | Acknowledge the limitation in docs. Password protects against casual access, not targeted sniffing. LAN is semi-trusted. |
| **Persistent share links (survive restart)** | "I generated a share link yesterday but restarted the server." | Requires database or persistent storage. Share links are meant to be temporary. | In-memory token store. Links expire when server restarts. This is a feature -- no stale links. Document the behavior. |
| **mDNS auto-discovery of the server** | "Other devices should find the server without scanning QR." | python-zeroconf adds native dependency and platform-specific behavior (firewall rules, mDNS responder conflicts on macOS). Marginal UX improvement over QR scanning. | QR code is already zero-friction. Device discovery in v1.1 means tracking *connected* devices, not *discovering* the server. mDNS is v2. |
| **Full Textual TUI framework** | "Use Textual for interactive terminal widgets." | Textual is a full application framework with event loops that conflict with uvicorn's async loop. Heavy dependency. | Rich (not Textual) is the right choice. `Live` display provides tables and layouts without event loop conflicts. |
| **Receive mode with custom upload forms** | "Let uploaders fill in name, email, description." | Custom form builder is scope creep. Turns drop box into a form submission tool. | Optional uploader name field only. For structured data collection, use a different tool. |
| **Rate limiting on password** | "Prevent brute-force attacks." | On a LAN, brute-forcing requires physical network proximity. Threat model does not justify the complexity. | Sufficient protection from bcrypt work factor. |
| **File-level permissions** | "Per-file read/write/share ACLs." | ACL system is massively complex. Way beyond v1.1. | Server-wide mode (full/read-only/receive) covers the use cases. |

---

## Expected Behavior Per Feature

### 1. Password Protection

**How it works in the ecosystem:**
- Windows file sharing: OS-level credential prompt per share
- uploadserver (PyPI): `--basic-auth user:pass` header-based, can require auth only for uploads
- FileBrowser: Login page with username/password, session-based
- EZ File Drop: PIN code for upload portals

**Expected behavior for this project:**
- CLI: `wifi-file-server ./files --password mysecret`
- First visit: Full-page password prompt (no access to anything until correct password entered)
- Auth mechanism: Server generates a session token on correct password. Stored in a cookie. All subsequent API requests validated by middleware. WebSocket connections also require the token (query param).
- No usernames. Single shared password. Token lives until browser is closed or server restarts.
- Wrong password: Clear error message, no lockout (LAN tool, not a bank)
- Server stores bcrypt hash of password, never the plaintext
- Combinable with all modes: `--password secret --read-only`, `--password secret --receive`

**Complexity: LOW.** One middleware class, one endpoint (`POST /api/auth`), one React component (password gate), config expansion. ~200-300 LOC.

**Existing code integration points:**
- `ServerConfig` in `config.py`: Add `password_hash: str | None` field
- `_build_parser()` in `cli.py`: Add `--password` argument
- `create_app()` in `main.py`: Add middleware before router mounting
- `apiFetch/apiPost/apiPatch/apiDelete` in `client.ts`: Cookie sent automatically by browser
- `/api/server-info` endpoint: Return `requires_password: bool` flag
- WebSocket connect in `useWebSocket.ts`: Append auth token to WS URL query params

### 2. Read-Only Mode

**How it works in the ecosystem:**
- FTP servers: Anonymous read-only vs authenticated read-write
- FileBrowser: Per-user role-based permissions (viewer, editor, admin)
- Python `http.server`: Inherently read-only (no upload handler)

**Expected behavior for this project:**
- CLI: `wifi-file-server ./files --read-only`
- Server blocks all mutating operations: upload, delete, rename, create folder, clipboard write, file request fulfillment
- HTTP: POST/PATCH/DELETE to file endpoints return 403 with clear JSON error
- UI: Upload button, delete, rename, create folder, file request "fulfill" button -- all hidden. Drag-and-drop overlay disabled. Toolbar shows only download/view actions.
- `/api/server-info` returns `read_only: true` so client knows to hide write controls
- Combinable with `--password`: `--password secret --read-only` = password-protected read-only

**Complexity: LOW.** Middleware intercepts mutating HTTP methods. Client checks a flag from server-info. ~100-150 LOC.

**Existing code integration points:**
- `ServerConfig` in `config.py`: Add `read_only: bool` field
- `_build_parser()` in `cli.py`: Add `--read-only` flag
- New middleware in `main.py`: Reject POST/PATCH/DELETE on `/api/files/*`, `/api/folders`, `/api/clipboard/*`
- `/api/server-info`: Return `read_only` flag
- `App.tsx`: Conditional rendering based on server-info response

### 3. Receive Mode / Digital Drop Box

**How it works in the ecosystem:**
- EZ File Drop: Branded upload page with custom fields, connected to cloud storage. Paid service.
- WeTransfer: Upload page with email delivery
- University submission portals: Upload form with student ID, assignment selection

**Expected behavior for this project:**
- CLI: `wifi-file-server ./files --receive`
- UI: Stripped-down page showing only: server name, upload zone (drag-and-drop + file picker), optional uploader name field, submit button, upload progress, success confirmation
- No file browsing, no file listing, no search, no preview, no clipboard, no file requests visible
- Uploaded files land in shared folder (optionally in auto-created subdirectories by uploader name or timestamp)
- Server operator sees uploads in terminal UI or by browsing the folder directly
- Combinable with `--password`: `--password secret --receive` = password-protected drop box
- Mutually exclusive with `--read-only`: CLI rejects `--read-only --receive` with clear error
- QR code still works (scan to open the drop box page)

**Complexity: MEDIUM.** Requires conditional rendering in React based on server mode. New minimal upload-only component reusing existing `useUpload` hook and `UploadPanel`. Server needs mode flag in config and server-info. ~400-500 LOC.

**Existing code integration points:**
- `ServerConfig`: Add `receive_only: bool` field (or better, a `ServerMode` enum: FULL, READ_ONLY, RECEIVE_ONLY)
- CLI validation: Reject `--read-only --receive` combination
- Middleware: In receive mode, allow only POST to `/api/files/upload` and GET to `/api/server-info`
- `App.tsx`: If `server_mode === "receive"`, render `ReceiveView` component instead of full file browser
- Reuse `useUpload` hook, `UploadPanel`, `UploadOverlay` components from v1.0

### 4. Expiring Share Links

**How it works in the ecosystem:**
- Dropbox: "Copy link" with optional expiry and password
- tfLink: One-time download URLs with view counters and auto-expiry
- Common pattern: `secrets.token_urlsafe(32)` -> store `{token: {path, expires_at}}` -> validate on access

**Expected behavior for this project:**
- UI: "Share" context menu action on each file row
- Click "Share" -> dialog with TTL selector (15min, 1hr, 6hr, 24hr) -> generates link -> copy to clipboard
- Generated URL format: `http://192.168.1.5:8000/share/{token}`
- Token endpoint validates token, checks expiry, serves file with Content-Disposition: attachment
- Expired links return 410 Gone with a clean "This link has expired" page
- Share links bypass password protection (the token IS the authentication)
- In-memory storage: Links do not survive server restart (acceptable for LAN tool)
- Server operator can list/revoke active share links (API endpoint, shown in terminal UI)
- Optional: Max download count (e.g., expires after 5 downloads or TTL, whichever first)

**Complexity: MEDIUM-HIGH.** Token generation is trivial, but full flow includes: backend token store, new endpoints (create/validate/list/revoke), React share dialog with TTL picker, share landing page, expired link page, and background cleanup task. ~500-700 LOC.

**Existing code integration points:**
- New service: `share_link_service.py` with in-memory token dict
- New router: `share_links.py` with create/validate/list/revoke endpoints
- New React components: `ShareDialog`, share landing page
- File row context menu: Add "Share" action alongside download/rename/delete
- Server-info: Include `sharing_enabled: bool` flag
- SPA catch-all in `main.py`: Route `/share/{token}` before the SPA fallback

### 5. Device Discovery Panel

**How it works in the ecosystem:**
- PairDrop: Circle of device icons with names, click to send files
- AirDrop: Grid of nearby device icons with names
- KDE Connect: Device list with name, type, battery status, features

**Expected behavior for this project:**
- Expand existing connection status dot into a clickable element
- Click opens a slide-out panel (reuse scratchpad panel pattern) showing:
  - List of connected devices: name, IP address, connection duration, device type icon (parsed from User-Agent)
  - Device count header
  - "You" indicator for current device
- Real-time updates via existing WebSocket infrastructure (new message type for device list changes)
- Server-side: ConnectionManager needs IP (from WebSocket scope `client.host`) and connect timestamp. New API endpoint to list connected devices.
- Terminal UI: Also displays this device list

**Complexity: LOW-MEDIUM.** Most infrastructure exists. ConnectionManager needs IP + timestamp fields. New WS message type, new API endpoint, new React panel. ~300-400 LOC.

**Existing code integration points:**
- `ConnectionManager` in `connection_manager.py`: Add `device_ips: dict[str, str]` and `connect_times: dict[str, float]`
- `websocket_endpoint` in `websocket.py`: Extract `websocket.client.host` on connect, store timestamp
- New WS message type: `DEVICE_LIST` in `enums.py`
- New API endpoint: `GET /api/devices` returns device list
- New React component: `DevicePanel.tsx` (slide-out, similar to `ScratchpadPanel`)
- `ConnectionStatus.tsx`: Make the status dot clickable to toggle panel

### 6. Rich Terminal UI

**How it works in the ecosystem:**
- ghtop: Rich-powered live terminal dashboard for GitHub events
- tui-plex: Textual app for Plex server monitoring
- OpenSpeedTest CLI: Minimal output, no dashboard

**Expected behavior for this project:**
- Replace plain `print()` output in `cli.py` with Rich `Live` dashboard
- Dashboard layout:
  - **Header row:** Server name, shared folder path, server URL, uptime
  - **QR Code panel:** ASCII QR (already generated via qrcode library)
  - **Devices table:** Name, IP, connected duration (from device discovery data)
  - **Activity log:** Recent uploads/downloads with timestamp, file size, device name
  - **Stats footer:** Total files served, bytes transferred, active connections
- Live updates as events occur (device connects, file transferred)
- Implementation: Run uvicorn via `uvicorn.Server.serve()` as asyncio task. Run Rich `Live` update loop as concurrent asyncio task. Events push to an asyncio queue.
- `--no-tui` flag: Fall back to plain `print()` output (for piped output, CI, logging)
- Graceful degradation: Detect non-interactive terminal and auto-disable TUI

**Complexity: MEDIUM-HIGH.** Rich rendering is straightforward, but uvicorn async integration and event collection require careful orchestration. Event bus pattern needed to collect events from file operations, WebSocket connections. ~600-800 LOC. New dependency: `rich`.

**Existing code integration points:**
- `cli.py`: Major rewrite of `main()` to use Rich `Console` and `Live`
- `config.py`: Add `tui_enabled: bool` field
- New module: `server/app/services/event_bus.py` for collecting server events
- File router (`files.py`): Emit events on upload/download/delete
- WebSocket router (`websocket.py`): Emit events on connect/disconnect
- New CLI flag: `--no-tui`

### 7. Network Speed Test

**How it works in the ecosystem:**
- OpenSpeedTest: XHR-based, sends/receives large payloads, measures throughput. Pure JS + static server.
- fast.com: Downloads progressively larger chunks, measures aggregate throughput
- LAN Speed Test (Totusoft): Native app, writes/reads test files for disk + network speed

**Expected behavior for this project:**
- UI: Speed test panel accessible from toolbar or header icon
- Download test: Client XHR GET to `/api/speedtest/download` returns stream of random bytes (10MB default). Client measures bytes received / time elapsed.
- Upload test: Client XHR POST with generated Blob to `/api/speedtest/upload`. Server discards data, returns byte count. Client measures bytes sent / time.
- Latency test: Multiple XHR pings to `/api/speedtest/ping`, measure round-trip min/avg/max.
- Results: Download speed (Mbps), upload speed (Mbps), latency (ms). Visual gauge or bar display.
- Duration: ~5 seconds per direction, ~15 seconds total.
- No external dependencies: `os.urandom()` server-side, `new Blob()` client-side.

**Complexity: MEDIUM.** Three new API endpoints, one React component with progress animation. XHR progress tracking pattern already implemented in `uploadWithProgress`. ~400-500 LOC.

**Existing code integration points:**
- New router: `speedtest.py` with download/upload/ping endpoints
- New React component: `SpeedTestPanel.tsx`
- Reuse XHR progress pattern from `client.ts` `uploadWithProgress`
- Toolbar: Add speed test button/icon

---

## Feature Dependencies

```
ServerConfig expansion (password_hash, server_mode enum, tui_enabled)
    |
    +-- Password Protection (middleware)
    |     +--enhances--> Receive Mode (password-protected drop box)
    |     +--enhances--> Expiring Share Links (share links bypass password)
    |
    +-- Server Mode (middleware) [FULL | READ_ONLY | RECEIVE_ONLY]
    |     +-- Read-Only Mode
    |     +-- Receive Mode
    |     +-- CONFLICT: read-only + receive are mutually exclusive
    |
    +-- Expiring Share Links (independent of auth/mode)
    |     +--requires--> File download endpoint (exists in v1.0)
    |
    +-- Device Discovery Panel
    |     +--requires--> ConnectionManager (exists in v1.0)
    |     +--enhances--> Terminal UI (device list in dashboard)
    |
    +-- Terminal UI (server-side only)
    |     +--requires--> Rich library (new dependency)
    |     +--enhances--> Speed Test (results in dashboard)
    |
    +-- Speed Test (fully independent)
```

### Critical Dependency Notes

- **Password + Read-Only + Receive are all middleware features.** They share the middleware pattern but are independent in logic. Build the middleware framework once, then each mode plugs in.
- **Read-Only conflicts with Receive.** `--read-only` blocks all writes. `--receive` requires uploads. CLI must reject the combination. Use a `ServerMode` enum (FULL, READ_ONLY, RECEIVE_ONLY) to enforce mutual exclusivity.
- **Expiring Share Links bypass Password.** The token in the URL IS the authentication. A valid share link does not require the server password. This is intentional -- share links distribute specific files to people who may not have the password.
- **Device Discovery feeds Terminal UI.** The terminal dashboard shows connected devices, so device tracking must be enhanced before the dashboard can display it.
- **Speed Test is fully standalone.** No dependencies on any other v1.1 feature. Can be built and shipped independently at any point.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Risk | Priority |
|---------|------------|---------------------|------|----------|
| Password Protection | HIGH | LOW | LOW | P1 |
| Read-Only Mode | HIGH | LOW | LOW | P1 |
| Receive Mode / Drop Box | MEDIUM-HIGH | MEDIUM | LOW | P1 |
| Device Discovery Panel | MEDIUM | LOW-MEDIUM | LOW | P2 |
| Expiring Share Links | MEDIUM | MEDIUM-HIGH | MEDIUM | P2 |
| Rich Terminal UI | MEDIUM | MEDIUM-HIGH | MEDIUM | P3 |
| Speed Test | LOW-MEDIUM | MEDIUM | LOW | P3 |

**Priority key:**
- **P1: Must have.** Password, read-only, and receive mode are the "access control + sharing" promise of v1.1. All three are middleware features sharing the same pattern. Ship together.
- **P2: Should have.** Device discovery is a quick win extending existing infrastructure. Expiring share links are the power-user sharing feature.
- **P3: Nice to have.** Terminal UI and speed test improve operator experience but do not affect end-user functionality. Can be deferred if scope needs to shrink.

---

## MVP Definition

### v1.1 Core (Ship Together -- Access Control Foundation)

- [ ] **Password Protection** -- The headline feature. Unblocks sharing on untrusted networks.
- [ ] **Read-Only Mode** -- Natural companion. Trivial once middleware pattern exists.
- [ ] **Receive Mode / Drop Box** -- Same middleware framework, different restriction. The novel sharing mode.

### v1.1 Full (Ship After Core -- Sharing & Discovery)

- [ ] **Device Discovery Panel** -- Quick win, extends existing ConnectionManager.
- [ ] **Expiring Share Links** -- The power-user sharing feature. Moderate complexity.

### v1.1 Polish (Ship Last)

- [ ] **Rich Terminal UI** -- Server operator experience only. No web client impact.
- [ ] **Network Speed Test** -- Diagnostic tool. Useful but not essential.

### Defer to v1.2+

- Gallery mode / slideshow (photo grid for image-heavy shares)
- Resumable/chunked transfers (important but complex, separate milestone)
- Custom branding for drop box page
- mDNS server discovery (advertise server on network)

---

## Competitor Feature Analysis

| Feature | PairDrop | LocalSend | FileBrowser | uploadserver | This Project (v1.1) |
|---------|----------|-----------|-------------|-------------|---------------------|
| Password protection | Room codes | None | Full user auth | `--basic-auth` | Single shared password via CLI |
| Read-only mode | N/A | N/A | Per-user roles | Auth-only-for-upload | Server-wide via `--read-only` |
| Receive/drop box | No | No | No | Upload-only by default | Dedicated UI via `--receive` |
| Expiring share links | Temp rooms (different) | No | Links (no expiry) | No | Token-based with TTL |
| Device list | Device circle UI | Nearby list | Admin user list | No | Panel with IP + duration |
| Terminal dashboard | N/A | Minimal output | N/A | None | Rich live dashboard |
| Speed test | No | No | No | No | Built-in LAN speed test |

**Key insight:** No single competitor offers receive mode, expiring share links, AND a speed test. Combined with v1.0's file management, preview, clipboard, and file requests, this creates a uniquely capable LAN sharing tool.

---

## Sources

- Codebase analysis: `server/app/cli.py`, `server/app/config.py`, `server/app/main.py`, `server/app/services/connection_manager.py`, `server/app/routers/files.py`, `server/app/routers/websocket.py`, `client/src/api/client.ts`, `client/src/hooks/useWebSocket.ts` -- HIGH confidence
- [FastAPI Security - First Steps](https://fastapi.tiangolo.com/tutorial/security/first-steps/) -- HIGH confidence
- [FastAPI Auth Middleware](https://github.com/code-specialist/fastapi-auth-middleware) -- MEDIUM confidence
- [Rich Live Display docs](https://rich.readthedocs.io/en/stable/live.html) -- HIGH confidence
- [OpenSpeedTest](https://github.com/openspeedtest/Speed-Test) -- MEDIUM confidence (speed test XHR pattern reference)
- [PairDrop](https://github.com/schlagmichdoch/PairDrop) -- MEDIUM confidence (competitor analysis)
- [EZ File Drop](https://www.ezfiledrop.com/) -- MEDIUM confidence (receive mode concept reference)
- [uploadserver PyPI](https://pypi.org/project/uploadserver/) -- MEDIUM confidence (auth mode reference)
- [Tokenized URLs explained](https://www.verimatrix.com/anti-piracy/faq/understanding-tokenized-urls-and-expiring-links-for-secure-access/) -- MEDIUM confidence (expiring link pattern)
- [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) -- HIGH confidence (evaluated and rejected for v1.1, deferred to v2)

---

*Feature research for: WiFi File Server v1.1 Share & Access Control*
*Researched: 2026-03-10*
