# Pitfalls Research

**Domain:** Adding access control, sharing modes, device discovery, terminal UI, and speed test to existing LAN file server (v1.1)
**Researched:** 2026-03-10
**Confidence:** HIGH (based on direct codebase analysis of all 40+ source files + verified external patterns)

## Critical Pitfalls

### Pitfall 1: Incomplete Write-Path Blocking in Read-Only Mode

**What goes wrong:**
Read-only mode blocks the obvious write endpoints (upload, delete, rename) but misses hidden write paths. The existing codebase has **eight distinct write surfaces** across three routers and WebSocket:

1. `POST /api/files/upload` -- file upload (`files.py:89`)
2. `DELETE /api/files` -- file/folder deletion (`files.py:208`)
3. `PATCH /api/files/rename` -- rename (`files.py:187`)
4. `POST /api/folders` -- create folder (`files.py:225`)
5. `POST /api/file-requests/{id}/fulfill` -- uploads a file via `upload_file()` internally (`file_requests.py:60`)
6. `POST /api/clipboard/` -- creates snippet, writes to `.wfs_data/clipboard.json` (`clipboard.py:26`)
7. `DELETE /api/clipboard/{id}` -- deletes snippet (`clipboard.py:61`)
8. WebSocket `snippet_update` message -- updates snippet content via WS, completely bypassing REST middleware (`websocket.py:61`)

Missing even one turns "read-only" into a false sense of security.

**Why it happens:**
Developers check the files router and forget clipboard, file-requests, and WebSocket message handlers. The `fulfill_file_request` endpoint is particularly sneaky -- it looks like a POST to a "request" resource but internally calls `upload_file()` on line 71, making it a filesystem write operation.

**How to avoid:**
Create a FastAPI dependency that checks `config.read_only` and raises `HTTPException(403)`. Apply it via `dependencies=[Depends(require_writable)]` at the router level for all three routers. For WebSocket, add a guard in the message routing `if/elif` chain in `websocket.py` before processing `snippet_update` messages.

**Warning signs:**
- Tests only cover `/api/files/upload` and `DELETE /api/files` in read-only mode
- No test for clipboard or file-request writes in read-only mode
- Users can still create snippets or fulfill file requests while server says "read-only"

**Phase to address:**
Access Control phase. Must be implemented as an exhaustive write-path audit, not a flag check on two endpoints.

---

### Pitfall 2: Auth Bypass via Direct URL Access (Downloads, Preview, WebSocket, SPA)

**What goes wrong:**
Password protection is added to API endpoints via middleware, but four distinct request patterns in the existing codebase bypass the centralized `apiFetch()` client:

1. **`downloadFile()`** in `client/src/api/files.ts:21-28` creates a raw `<a>` tag pointing to `/api/files/download?path=...`. This is a direct browser navigation, not an XHR. Custom Authorization headers cannot be attached to anchor tag navigations.

2. **`downloadAsZip()`** in `client/src/api/files.ts:34-53` uses raw `fetch()` instead of `apiFetch()`. No auth header injection point.

3. **WebSocket connection** in `hooks/useWebSocket.ts:38-39` connects to `/ws?device_name=...`. The browser's WebSocket API does not support custom request headers on the upgrade handshake in all browsers.

4. **Preview URLs** are loaded as `src` attributes on `<img>`, `<video>`, `<audio>` elements (see PreviewModal and various preview components). Browsers do not send custom headers with media element source requests.

5. **SPA catch-all** route `/{path:path}` in `main.py:61-68` serves static files and `index.html`. If this is not behind auth, the entire UI loads without authentication.

**Why it happens:**
Header-based auth (Authorization: Bearer) works for XHR/fetch requests but fails for every other request type the browser makes. The existing client has five `api*` helper functions in `client.ts` that all go through `fetch()` -- adding an auth header there is tempting but covers only half the surface area.

**How to avoid:**
Use **cookie-based authentication**. On the LAN HTTP context (no HTTPS available), cookies are the only mechanism the browser automatically sends with every request type: XHR, anchor tag navigation, img/video/audio src loads, WebSocket upgrade handshakes, and direct URL access.

Implementation:
- On successful password entry, set an HttpOnly cookie with a session token
- Validate the cookie in FastAPI middleware that runs before ALL routes (API, WebSocket, SPA catch-all)
- For WebSocket, extract the cookie from `websocket.cookies` during the handshake
- Note: the existing CORS middleware has `allow_credentials` NOT set to True (see `main.py:32`) -- this must remain false with `allow_origins=["*"]` per CORS spec, but cookie-based auth works because the server and frontend are same-origin in production

**Warning signs:**
- User logs in via password screen, but pasting `/api/files/download?path=secret.txt` in an incognito window downloads the file
- WebSocket connects and receives toasts without authentication
- Media previews load without login

**Phase to address:**
Access Control phase. This is the most critical architectural decision -- choosing cookies vs headers determines the entire auth implementation.

---

### Pitfall 3: Dropbox/Receive Mode Allows Path Manipulation Outside Upload Directory

**What goes wrong:**
Receive mode creates a separate upload-only interface, but the existing upload endpoint accepts a `path` query parameter (see `files.py:92`: `path: str = Query("")`). If the dropbox reuses this endpoint, an attacker can POST with `path=../../other_folder` and write files anywhere within the shared folder, not just the dropbox directory.

The existing `resolve_safe_path()` in `file_service.py:43` validates paths against `config.shared_folder` -- it prevents escaping the shared folder entirely, but does NOT enforce a dropbox subdirectory constraint. A path like `path=documents/` is valid and writes to `shared_folder/documents/` instead of the dropbox.

**Why it happens:**
The dropbox reuses the existing `upload_file()` service function for less code duplication. But that function was designed for full-access users, not constrained uploaders.

**How to avoid:**
For the dropbox upload endpoint:
1. Create a dedicated route (`POST /api/dropbox/upload`) that does NOT accept a `path` parameter
2. Hard-code the upload destination to the dropbox directory (e.g., `shared_folder/inbox/`)
3. The dropbox endpoint should call `upload_file()` with a fixed path, ignoring any client-provided path

Do NOT expose the file listing endpoint to dropbox users -- they should see only an upload form, not the shared folder contents.

**Warning signs:**
- Dropbox endpoint accepts `path` query parameter from the client
- Tests verify upload works but do not verify path parameter is ignored
- Files uploaded via dropbox appear in arbitrary subdirectories

**Phase to address:**
Sharing phase -- receive mode/dropbox implementation.

---

### Pitfall 4: Share Link Tokens Leaked in Logs, Broadcasts, and Browser History

**What goes wrong:**
Expiring share links generate tokens embedded in URLs (e.g., `/share/abc123def456`). These tokens appear in:

1. **Uvicorn access logs** -- uvicorn logs every request by default: `INFO: 192.168.1.5 - "GET /share/abc123def456 HTTP/1.1" 200`
2. **WebSocket toast broadcasts** -- the existing pattern (see `files.py:116-126`) broadcasts file activity to all connected devices. If share link downloads broadcast too, the token leaks to all viewers
3. **Browser history** -- the share link URL is recorded in the browser's address bar

On a LAN where multiple people share a screen or see the server terminal, tokens in logs and broadcasts defeat the purpose of limited sharing.

**Why it happens:**
Developers focus on token generation and expiration logic. They forget that uvicorn logs every URL by default and the existing WebSocket toast pattern broadcasts file download events to all connected clients.

**How to avoid:**
- Store tokens **server-side** with metadata (file path, expiry, remaining uses) in a dict. The token is an opaque random string; the file path is NEVER encoded in the URL
- Do NOT include tokens or file paths in toast broadcasts for share link downloads. Just broadcast "A file was downloaded via share link"
- Consider adding the share link path to uvicorn's log exclusion filter, or accept that the opaque token in logs reveals nothing without server-side lookup
- Server-side storage also enables revocation

**Warning signs:**
- Token values visible in terminal output
- Toast messages include the file path when someone downloads via share link
- No token revocation mechanism exists

**Phase to address:**
Sharing phase -- expiring share links.

---

### Pitfall 5: Terminal UI and Uvicorn Fight for stdout/stderr Control

**What goes wrong:**
A Rich terminal dashboard (live stats, connected devices, transfer progress) and uvicorn both write to the same terminal, creating three conflicts:

1. **Interleaved output**: Rich's Live display redraws the screen with ANSI escape codes, but uvicorn prints access log lines between redraws, producing garbled output
2. **Cursor position corruption**: Rich positions the cursor to redraw specific regions. Uvicorn's log output shifts the cursor, corrupting the dashboard layout
3. **Signal handler conflict**: Rich's `Live` context manager, uvicorn, and the existing `cli.py:87` `KeyboardInterrupt` handler all compete for SIGINT. Three SIGINT handlers create race conditions on Ctrl+C

The existing `cli.py` starts uvicorn via `uvicorn.run("server.app.main:app", host=host, port=port)` on line 86 -- this call blocks and owns the terminal.

**Why it happens:**
Uvicorn is designed to own the terminal. Rich's Live display is also designed to own the terminal. Running both simultaneously without coordination is undefined behavior.

**How to avoid:**
- Suppress uvicorn's default logging by passing `log_config=None` to `uvicorn.run()`, then attach a `RichHandler` to uvicorn's logger that renders through the dashboard's Console object
- Use Rich's `Console(stderr=True)` for the dashboard if you want to keep some uvicorn output on stdout
- Alternatively, use Rich's alternate screen buffer (`Console(screen=True)`) to fully separate the dashboard from log output
- For Ctrl+C handling, ensure the Rich Live context wraps the uvicorn run call, so cleanup order is deterministic

**Warning signs:**
- Terminal output flickers or garbles during file transfers
- Ctrl+C does not cleanly stop the server (hangs or produces traceback)
- Log lines appear inside the dashboard, corrupting the layout

**Phase to address:**
Terminal UI phase. Must account for uvicorn's logging behavior from the start.

---

### Pitfall 6: mDNS Device Discovery Silently Fails on Most Networks

**What goes wrong:**
mDNS/Zeroconf (the standard for LAN service discovery) uses multicast UDP on port 5353. Many common network environments silently block this:

1. **macOS firewall** in "Block all incoming connections" mode blocks mDNS responses
2. **Corporate/university WiFi** with AP isolation prevents multicast between devices
3. **Guest networks** almost always have client isolation enabled
4. **Windows Defender Firewall** blocks incoming multicast on "Public" network profiles (the default for new WiFi connections)

The server starts, registers its mDNS service, but zero clients discover it. No error is raised -- mDNS just silently fails. The developer tests on their home network where it works perfectly.

**Why it happens:**
Multicast UDP is a "best effort" protocol. When blocked, there is no error -- packets are simply dropped. The `Zeroconf()` constructor and `register_service()` succeed regardless of whether any other device can actually receive the advertisements.

**How to avoid:**
- Treat mDNS as a **best-effort convenience**, not a requirement. The QR code + URL approach (already working in v1.0) must remain the primary connection method
- Add diagnostic logging: if the mDNS service registers but no browse queries are received within 10 seconds, log a warning
- Display "Discoverable on local network" in the terminal UI only when mDNS registration succeeds. Show "Discovery unavailable -- use QR code or URL" otherwise
- When calling `Zeroconf(interfaces=...)`, pass only the LAN IP that `detect_primary_lan_ip()` already identifies. Do NOT use the default (all interfaces), which registers on VPN, Docker bridge, and loopback

**Warning signs:**
- Feature works in development but users report "can't find server"
- No error messages when discovery fails
- Test suite only tests mDNS registration, not actual discovery

**Phase to address:**
Connectivity phase -- device discovery. Must include graceful fallback.

---

### Pitfall 7: Speed Test Saturates LAN, Disrupts Active Transfers and WebSocket

**What goes wrong:**
A network speed test works by sending large payloads to measure throughput. On a shared LAN link, this deliberately saturates bandwidth. If file transfers are in progress:

1. Active uploads/downloads slow to a crawl or time out
2. The speed test reports inaccurate results (bandwidth is shared with transfers)
3. WebSocket connections may drop -- the existing `ConnectionManager.broadcast()` catches send exceptions and disconnects dead connections (`connection_manager.py:35-38`). During bandwidth saturation, slow sends can trigger these false-positive disconnections

**Why it happens:**
Internet speed tests (speedtest.net) are designed for idle connections. A LAN file server is actively transferring files. The shared LAN link (typically 100 Mbps or 1 Gbps) has no QoS -- the speed test traffic competes equally with file transfer traffic.

**How to avoid:**
- Check for active transfers before starting a speed test. The frontend has `useUpload.isUploading` and the backend has `manager.active_connections` to detect activity
- Use a small payload (5-10 MB, completing in 1-2 seconds) rather than a sustained saturation test. LAN speed is stable and can be estimated from a brief burst
- Run the speed test on a separate HTTP request, not the existing WebSocket connection, to avoid disrupting real-time notifications
- Display the result as "estimated" since LAN speed varies by WiFi vs ethernet, concurrent activity, and device capabilities

**Warning signs:**
- Users report uploads failing or stalling when speed test runs
- WebSocket disconnects during speed test (visible as "reconnecting" banner)
- Speed test reports wildly different numbers on consecutive runs

**Phase to address:**
Connectivity phase -- speed test implementation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Checking `read_only` per-endpoint instead of router-level dependency | Faster to implement | Every new endpoint needs the check; forgotten endpoints are security holes | Never -- use `dependencies=[Depends(require_writable)]` on the router |
| Storing CLI password in plaintext in `ServerConfig` | Simple parsing, direct comparison | Process args visible via `ps aux`; config object holds cleartext | Acceptable for v1.1 -- password is transient (not persisted to disk), LAN context has limited threat model |
| In-memory dict for share link tokens | No database, instant lookups | Tokens lost on server restart; cannot scale to multiple workers | Acceptable for v1.1 -- single-worker LAN server. Restart = all links expire early, which is safe |
| Hard-coding dropbox directory to `shared_folder/inbox/` | Simple, predictable | Not configurable per-user | Acceptable for v1.1 -- add `--dropbox-dir` CLI flag later if needed |
| Reusing `upload_file()` for dropbox without wrapper | Less code duplication | Caller must remember to override path param; dropbox constraints not enforced by the function | Never -- create `dropbox_upload()` wrapper that enforces the fixed path and delegates |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Password auth + WebSocket | Adding auth middleware to HTTP routes only; WebSocket connects unauthenticated | Check auth cookie in `websocket_endpoint()` before `await websocket.accept()`. Reject with `websocket.close(code=4001)` |
| Password auth + file downloads | Auth header in XHR, but `downloadFile()` at `files.ts:21` uses `<a href=...>` which sends no headers | Cookie-based auth. Browser sends cookies with anchor tag navigations |
| Password auth + media preview | Auth on API calls, but `<img src="/api/files/preview?path=...">` sends no custom headers | Cookie-based auth covers all same-origin media loads |
| Password auth + SPA catch-all | Auth on `/api/*` routes, but SPA at `/{path:path}` serves `index.html` unprotected | Include SPA catch-all in auth middleware scope. Without password, return login page, not app |
| Read-only + clipboard WS | REST clipboard endpoints blocked, but `snippet_update` WS message at `websocket.py:61` still writes | Add read-only guard in WebSocket message routing before processing `snippet_update` |
| Read-only + file request fulfill | `fulfill_file_request()` at `file_requests.py:60` calls `upload_file()` internally | Block the fulfill endpoint in read-only mode |
| Read-only + frontend UI | Server blocks writes but UI still shows upload button, delete button, rename option | Server should expose `read_only` flag via `/api/info` endpoint; frontend hides write controls when true |
| Terminal UI + uvicorn | Both write to stdout simultaneously | Suppress uvicorn's `log_config`, redirect through Rich Console |
| Speed test + active transfers | Speed test saturates bandwidth during file transfer | Check `manager.active_connections` count and warn before starting |
| mDNS + multiple interfaces | `Zeroconf()` defaults to all interfaces; registers on VPN, Docker, loopback | Pass `interfaces=[lan_ip]` using the IP from `detect_primary_lan_ip()` |
| Share links + CORS | Share links may be accessed from different origin if shared via messaging | Share link routes should not require CORS since they serve files directly; ensure `Content-Disposition` is set |
| Dropbox + existing upload | Dropbox reuses `/api/files/upload` which accepts `path` query param | Dedicated `/api/dropbox/upload` endpoint that ignores path |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Share link token linear scan | Imperceptible at 10 links | Use dict keyed by token, not a list | 1000+ active links (possible with automation) |
| mDNS browse callback fires per-device | Each callback triggers WebSocket broadcast | Debounce discovery updates; batch-broadcast at most once per second | 20+ devices on network continuously joining/leaving |
| Speed test pre-allocates payload in memory | Server memory spikes during test | Stream random bytes from `os.urandom()` generator, do not pre-allocate | Payload > available RAM |
| Terminal UI re-renders per WebSocket event | Dashboard flickers, CPU spikes | Throttle to 2-4 FPS. Batch state changes, redraw on timer | 5+ concurrent uploading devices |
| Password check on every request | Adds latency to all API calls | Cache session validation result in middleware; check cookie signature, not database | Not a real issue for LAN but good practice |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Password in URL query parameter (`?password=secret`) | Visible in browser history, server logs, proxy logs | Send via POST body for initial auth; use cookie for subsequent requests |
| Encoding file path in share link token (JWT-style) | Token decoded reveals file structure; no revocation possible | Store tokens server-side. Token is opaque random string; path stored in server dict |
| No rate limiting on password attempts | Brute force on simple passwords takes seconds on LAN | 5 attempts per IP per minute. Progressive delay via `asyncio.sleep()` |
| Password comparison via `==` | Timing attack reveals password character by character | Use `hmac.compare_digest()` for constant-time comparison |
| Share tokens survive server restart (if accidentally persisted) | Stale tokens provide access without current password | Tie tokens to server session. In-memory storage naturally expires on restart |
| Dropbox upload accepts executable files | Malicious uploads on shared LAN | Acceptable for LAN context -- host controls what they do with files. Document the risk |
| Auth cookie without expiry | Browser remembers password forever | Set cookie `max-age` to session lifetime (e.g., 24 hours) |
| Auth cookie accessible to JavaScript | XSS can steal session | Set `HttpOnly` flag on auth cookie |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Password prompt on every page load (no session persistence) | Unusable -- entering password for every navigation | Set session cookie on first auth; persists for browser session |
| Read-only mode hides upload button but API still accepts writes | Users with dev tools or API knowledge can bypass | Server blocks writes AND frontend hides controls. Server is the authority |
| Dropbox link shows full file browser | Defeats purpose -- uploader sees all existing files | Dropbox has its own minimal page: upload area only, no file list, no navigation |
| Share link shows "expired" with dead-end page | User stuck with no action available | Show "This link has expired" with server URL and QR code so they can request a new link |
| Device discovery lists stale/phantom devices | Confusing device list with entries for disconnected devices | Set TTL on discovered services; remove after 30s of no mDNS advertisement; cross-reference with WebSocket `active_connections` |
| Speed test shows raw bytes/second | Meaningless to non-technical users | Show "Fast (94 MB/s)" with qualitative label plus estimated time for common file sizes |
| Terminal dashboard unreadable on 80-column terminals | Dashboard wraps and becomes gibberish | Detect terminal width via `shutil.get_terminal_size()`. Show compact view below 100 columns |
| Password-protected server still shows QR code that leads to login wall | User scans QR, gets confused by password prompt on phone | QR code page or terminal should indicate "Password protected" visually |

## "Looks Done But Isn't" Checklist

- [ ] **Password protection:** Incognito browser cannot access `/api/files/download?path=file.txt` without auth cookie
- [ ] **Password protection:** WebSocket connection rejected without auth cookie (check `websocket.cookies`)
- [ ] **Password protection:** Media preview `<img src="/api/files/preview?...">` requires auth
- [ ] **Password protection:** SPA `index.html` requires auth (catch-all route is protected)
- [ ] **Password protection:** Login page itself does NOT require auth (infinite redirect otherwise)
- [ ] **Password protection:** Share link routes work WITHOUT password (they have their own token auth)
- [ ] **Read-only mode:** Clipboard snippet creation returns 403
- [ ] **Read-only mode:** WebSocket `snippet_update` message is silently rejected (no crash)
- [ ] **Read-only mode:** File request fulfillment (`POST /api/file-requests/{id}/fulfill`) returns 403
- [ ] **Read-only mode:** Drag-and-drop upload is blocked (not just the upload button hidden)
- [ ] **Read-only mode:** Folder creation returns 403
- [ ] **Read-only mode:** Frontend hides ALL write controls (upload, delete, rename, new folder, clipboard create)
- [ ] **Dropbox:** `path` query parameter is ignored -- uploads always go to dropbox directory
- [ ] **Dropbox:** File listing endpoint is NOT accessible from the dropbox URL
- [ ] **Dropbox:** Dropbox page works WITHOUT server password (if password-protected, dropbox should still be open for uploads)
- [ ] **Share links:** Expired link returns 410 Gone (not 404 -- different semantics)
- [ ] **Share links:** Token is NOT visible in WebSocket toast broadcasts
- [ ] **Share links:** All tokens expire on server restart (in-memory store)
- [ ] **Share links:** Share links work without password auth (their own token is the auth)
- [ ] **Device discovery:** mDNS failure does not crash server or block startup
- [ ] **Device discovery:** Works when device has multiple network interfaces (VPN, Docker bridge)
- [ ] **Terminal UI:** Ctrl+C cleanly stops both dashboard and uvicorn (no traceback, no hang)
- [ ] **Terminal UI:** Output not garbled when uploads trigger log messages during dashboard rendering
- [ ] **Terminal UI:** Dashboard gracefully degrades on narrow terminals (< 80 columns)
- [ ] **Speed test:** Does not cause WebSocket disconnections
- [ ] **Speed test:** Shows warning if active transfers detected before running

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Incomplete read-only blocking | LOW | Add router-level `Depends(require_writable)` -- no data model changes |
| Auth bypass via direct URL | MEDIUM | Retrofit cookie-based auth. Change all `apiFetch/apiPost` to include `credentials: 'same-origin'`. Add cookie-setting endpoint. Add middleware for ALL routes |
| Dropbox path manipulation | LOW | Override path parameter to fixed value in dedicated endpoint |
| Token leak in logs | LOW | Token is opaque -- leak reveals nothing. But filter toast broadcasts |
| Terminal UI garbling | MEDIUM | Restructure logging through Rich Console. Change how `uvicorn.run()` is called in `cli.py` |
| mDNS silent failure | LOW | Add timeout diagnostic and fallback messaging |
| Speed test disrupting transfers | LOW | Add pre-check for active transfers. Small code change |
| Password in header vs cookie (wrong choice) | HIGH | Retrofitting from header-based to cookie-based auth touches every API call, download function, preview component, and WebSocket connection. Make this decision FIRST |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Incomplete read-only blocking | Access Control | Test all 8 write endpoints return 403 in read-only mode |
| Auth bypass via direct URL | Access Control | Incognito browser test: direct URL access to every resource type |
| Password timing attack | Access Control | Code review: verify `hmac.compare_digest()` usage |
| Password brute force | Access Control | Test: 6th failed attempt within 60s returns 429 |
| Dropbox path manipulation | Sharing | Test: `curl -X POST /api/dropbox/upload?path=../../` writes to inbox only |
| Share token in logs | Sharing | Visual check: token is opaque in terminal output |
| Share token in broadcasts | Sharing | Test: WebSocket toast for share download contains no token or file path |
| Share link + password interaction | Sharing | Test: share link works in incognito without server password |
| Terminal UI + uvicorn conflict | Terminal UI | Visual test: upload file while dashboard is running |
| Terminal UI on narrow terminal | Terminal UI | Test: resize terminal to 60 columns during operation |
| mDNS silent failure | Device Discovery | Test on network with client isolation (or mock multicast failure) |
| Speed test disruption | Speed Test | Test: run speed test during active upload; verify upload completes |
| Speed test + WebSocket | Speed Test | Test: verify no WebSocket disconnects during speed test |

## Sources

- Direct codebase analysis: `server/app/routers/files.py` (7 write endpoints), `clipboard.py` (2 write endpoints), `file_requests.py` (fulfill calls `upload_file`), `websocket.py` (WS message routing bypasses REST middleware)
- Direct codebase analysis: `client/src/api/client.ts` (centralized API helpers), `files.ts` (`downloadFile` anchor tag bypass, `downloadAsZip` raw fetch bypass), `hooks/useWebSocket.ts` (WS connection has no auth), `hooks/useUpload.ts` (XHR upload has no auth cookie handling)
- Direct codebase analysis: `server/app/main.py` (SPA catch-all at line 61, CORS config at line 30-37)
- [FastAPI Security Tutorial](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI WebSocket Authentication Patterns](https://medium.com/@keshariaditya90/secure-fastapi-websocket-fixing-dependency-injection-errors-26fd10f97be1)
- [Implementing Auth on WebSocket with FastAPI](https://peterbraden.co.uk/article/websocket-auth-fastapi/)
- [OWASP Path Traversal](https://owasp.org/www-community/attacks/Path_Traversal)
- [Tokenized URLs and Expiring Links](https://www.verimatrix.com/anti-piracy/faq/understanding-tokenized-urls-and-expiring-links-for-secure-access/)
- [Auth0 Token Best Practices](https://auth0.com/docs/secure/tokens/token-best-practices)
- [Python Zeroconf Library](https://github.com/python-zeroconf/python-zeroconf)
- [Rich Terminal Console in Background Threads](https://github.com/Textualize/rich/issues/2665)
- [Unified Logging for Uvicorn/FastAPI](https://pawamoy.github.io/posts/unify-logging-for-a-gunicorn-uvicorn-app/)
- [Uvicorn Settings -- log_config](https://www.uvicorn.org/settings/)
- [LAN Bandwidth Speed Testing](https://www.junian.net/tech/local-area-network-bandwidth-speed-test/)
- [Confluence Read-Only Mode API Design](https://developer.atlassian.com/server/confluence/how-to-make-your-add-on-compatible-with-read-only-mode/)

---
*Pitfalls research for: WiFi File Server v1.1 feature additions*
*Researched: 2026-03-10*
