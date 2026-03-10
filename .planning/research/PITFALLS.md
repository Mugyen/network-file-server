# Pitfalls Research

**Domain:** Adding WebSocket tunnel relay server and remote mount agent to existing LAN file sharing app (v1.2)
**Researched:** 2026-03-11
**Confidence:** HIGH (based on codebase analysis of existing WebSocket/auth infra + verified external patterns for tunnel relay architectures)

## Critical Pitfalls

### Pitfall 1: No Backpressure on File Streaming Over WebSocket Causes OOM on Relay

**What goes wrong:**
A browser user downloads a 2GB video via the relay. The relay reads chunks from the agent's WebSocket faster than it can push them to the browser's HTTP response (or vice versa for uploads). Without backpressure, the relay buffers the entire file in memory. With 5 concurrent downloads of large files, the relay process crashes with OOM on a small cloud VM.

FastAPI's WebSocket implementation (via Starlette) does not provide built-in backpressure for binary streaming. The `websocket.send_bytes()` call returns when data is queued in the write buffer, not when the remote side has consumed it. If the consumer is slow, the buffer grows unboundedly.

**Why it happens:**
WebSocket has no native flow control at the application layer. TCP provides flow control at the transport layer, but Python's asyncio buffering sits between your application and TCP. The relay sits in the middle of two connections (browser HTTP <-> relay <-> agent WebSocket), each with independent speeds. Developers test with small files on localhost where both sides are fast, so the mismatch never surfaces.

**How to avoid:**
- Implement chunk-level flow control in the tunnel protocol: the relay sends a chunk to the browser, waits for the write to drain (`await writer.drain()` equivalent), then requests the next chunk from the agent. Never pipeline more than N chunks (e.g., 2-4) ahead.
- Use `asyncio.Queue(maxsize=N)` between the WebSocket receiver and HTTP response writer. When the queue is full, the receiver blocks, which applies TCP-level backpressure to the agent connection.
- Set explicit `max_size` on WebSocket connections (default is 1MB in the `websockets` library, but Starlette/uvicorn may differ). For binary file streaming, use chunked binary frames (64KB-256KB per frame), not one giant message.
- Monitor relay memory usage. Alert if RSS exceeds expected bounds.

**Warning signs:**
- Relay memory grows linearly with number of concurrent downloads
- Large file downloads succeed on fast networks but fail on slow consumer connections
- `MemoryError` or process killed by OS OOM killer under load

**Phase to address:**
Tunnel protocol design phase. This is the most critical architectural decision for the relay -- get it wrong and everything else is unstable.

---

### Pitfall 2: Request-Response Correlation Fails Under Concurrent Access

**What goes wrong:**
Multiple browser users hit the same mount simultaneously. The relay forwards each HTTP request through the single WebSocket tunnel to the agent. The agent processes requests and sends responses back. Without proper correlation, Response B arrives and gets delivered to Browser A's pending request, corrupting both downloads.

This is especially dangerous for file downloads where a misrouted response silently delivers the wrong file content -- no error, just wrong data.

**Why it happens:**
A single WebSocket connection is a single bidirectional byte stream with no built-in request multiplexing. Developers build a working prototype with one browser tab, see it work, and assume concurrency is handled. The bug only manifests when two requests are in-flight simultaneously, which is common in practice (browser makes parallel requests for directory listing + favicon + preview thumbnails).

**How to avoid:**
- Assign a unique request ID (UUID4 or monotonic counter) to every request the relay forwards through the tunnel. The agent must echo this ID in every response frame.
- On the relay side, maintain a `dict[str, asyncio.Future]` mapping request IDs to pending responses. When a response frame arrives, resolve the correct Future by its ID.
- Set a timeout on each Future (e.g., 30 seconds). If the agent never responds, return 504 Gateway Timeout to the browser instead of hanging forever.
- For streaming responses (file downloads), the request ID must be present on every chunk frame, not just the first. The relay demultiplexes chunks to the correct HTTP response by ID.

**Warning signs:**
- File downloads occasionally return wrong content (different file than requested)
- Requests hang indefinitely when multiple users browse simultaneously
- Download progress jumps backwards or forwards unexpectedly

**Phase to address:**
Tunnel protocol design phase. The wire protocol must include correlation IDs from day one -- retrofitting is a rewrite.

---

### Pitfall 3: Agent Reconnection Drops In-Flight Requests Silently

**What goes wrong:**
The agent's WebSocket connection drops (network blip, laptop sleep, WiFi switch). The agent reconnects within seconds. But all in-flight requests on the old connection are now orphaned: the relay has pending HTTP responses waiting for data that will never arrive. Browser users see infinite spinners or partial downloads with no error message.

Worse: if the relay does not clean up the old mount state before the agent reconnects, two tunnel connections exist briefly for the same mount code, creating split-brain routing.

**Why it happens:**
Reconnection logic focuses on re-establishing the WebSocket. Developers forget that reconnection is not just "connect again" -- it requires state reconciliation. The relay must cancel all in-flight requests, return errors to waiting browsers, and atomically swap the old tunnel for the new one.

**How to avoid:**
- On agent disconnect, the relay must immediately fail all pending Futures for that mount with a `502 Bad Gateway` or `503 Service Unavailable` response. Do not wait for the agent to reconnect.
- On agent reconnect, verify the mount code + agent secret before accepting. Atomically replace the old WebSocket reference. Never allow two tunnels for the same mount.
- Implement exponential backoff with jitter in the agent's reconnection logic (1s, 2s, 4s, 8s... capped at 60s). Include jitter to prevent thundering herd if the relay restarts.
- Add a "mount health" status that the relay tracks: CONNECTED, RECONNECTING, DISCONNECTED. Browser requests during RECONNECTING get a retryable 503 with `Retry-After` header.

**Warning signs:**
- Browser shows infinite spinner after agent briefly disconnects
- Partial file downloads (first half from old connection, nothing after)
- Two WebSocket connections from same agent exist simultaneously in relay's connection registry
- Agent reconnects but old pending requests are never resolved

**Phase to address:**
Tunnel protocol design phase (reconnection semantics) and relay implementation phase (in-flight request cleanup).

---

### Pitfall 4: Mount Code Brute Force Gives Unrestricted Access to Someone's Filesystem

**What goes wrong:**
Mount codes are short (4-6 characters for usability). An attacker iterates through all possible codes and accesses any active mount. Since the mount exposes the user's local filesystem (read and potentially write access), this is a severe security issue -- the relay becomes a tool for filesystem exfiltration.

With a 6-character alphanumeric code, there are ~2.2 billion combinations. But if codes use a smaller alphabet (e.g., lowercase + digits = 36 chars, 4 characters = 1.7M combinations), brute force is trivial at scale.

**Why it happens:**
Developers optimize for usability (short, easy-to-type codes) without considering that the relay is internet-facing. On LAN, short codes are fine because attackers need physical network access. On the public internet, anyone can probe the relay.

**How to avoid:**
- Use at minimum 6-character codes from a 36-character alphabet (lowercase + digits), yielding ~2.2 billion combinations. 8 characters is better.
- Implement aggressive rate limiting on mount code lookups: 5 failed attempts per IP per minute, then block for 10 minutes. Use `429 Too Many Requests`.
- Support optional per-mount passwords (reuse the existing `--password` infrastructure from v1.1). The mount code routes to the mount, but the password gates access to the files.
- Log failed mount code attempts. Alert if a single IP tries more than 20 codes in an hour.
- Consider making codes time-scoped: a code created at time T is only valid for lookups within the mount's TTL window. Expired codes return 410 Gone, not 404 (prevents enumeration of whether a code was ever valid).

**Warning signs:**
- No rate limiting on the mount code lookup endpoint
- Mount codes shorter than 6 characters
- No logging of failed mount code attempts
- No per-mount password option

**Phase to address:**
Relay server implementation phase. Rate limiting must be present from the first public deployment.

---

### Pitfall 5: Relay Becomes an Open Proxy for Arbitrary Filesystem Access

**What goes wrong:**
The relay proxies browser HTTP requests to the agent. If the relay does not validate or sanitize the request path, an attacker could craft requests that make the agent serve files outside the intended shared directory. The agent's existing `resolve_safe_path()` (in `file_service.py:43`) validates against `config.shared_folder`, but the relay adds a new attack surface: the relay-to-agent protocol must faithfully transmit the path, and the agent must re-validate it.

Additionally, if the tunnel protocol allows the browser to specify arbitrary HTTP methods or headers, the agent could be tricked into performing unintended operations.

**Why it happens:**
The relay is a pure proxy -- it is tempting to pass through raw HTTP requests verbatim. But "pure proxy" does not mean "zero validation." The relay should only forward a constrained set of operations (list directory, download file, upload file), not arbitrary HTTP.

**How to avoid:**
- Define an explicit set of tunnel message types (enum): `LIST_DIR`, `DOWNLOAD_FILE`, `UPLOAD_FILE`, `GET_PREVIEW`, `GET_INFO`. Do NOT proxy raw HTTP requests through the tunnel.
- The agent must re-validate every path against `config.shared_folder` using the existing `resolve_safe_path()`. Never trust the relay to have validated paths.
- The relay should reject requests with path traversal patterns (`../`, encoded variants) before even forwarding to the agent, as defense in depth.
- Never expose the agent's full FastAPI app through the tunnel. The agent should have a dedicated, minimal request handler for tunnel operations, separate from the LAN server endpoints.

**Warning signs:**
- Tunnel protocol forwards raw HTTP request bytes instead of structured messages
- Agent reuses the same route handlers for both LAN and tunnel requests
- No path validation on the relay side (only on agent side)
- Tunnel supports arbitrary HTTP methods beyond GET/POST

**Phase to address:**
Tunnel protocol design phase. The message type enum must be defined before any implementation.

---

### Pitfall 6: Existing LAN Mode Breaks When Agent Code Is Added

**What goes wrong:**
The v1.2 agent functionality is added to the same codebase. Import-time side effects, new dependencies, or configuration changes break the existing LAN server mode. Users who never use remote mounts find that `wfs share ~/Downloads` no longer works because the codebase now requires a relay URL, or the agent's WebSocket client library conflicts with the server's WebSocket server code, or new CLI flags changed the argument parsing.

**Why it happens:**
The LAN server and the remote mount agent are fundamentally different programs that happen to share some code (file service, path validation). Developers add agent code to the existing server module, creating tight coupling. A bug in agent initialization crashes the server even when agent mode is not being used.

**How to avoid:**
- Keep the agent as a separate CLI command (`wfs mount ~/Downloads` vs `wfs share ~/Downloads`). The agent command should import only what it needs from the shared codebase.
- The relay server is a completely separate deployment -- it does NOT share code with the LAN server beyond possibly shared model definitions.
- Use lazy imports: the agent's WebSocket client library should only be imported when `wfs mount` is invoked, not at module load time.
- Regression test: the existing LAN server test suite must pass with zero modifications after adding agent code. If any test needs changes, coupling has been introduced.

**Warning signs:**
- `wfs share ~/Downloads` fails with import errors for new dependencies
- Existing tests fail after adding agent module
- `--help` output for `wfs share` shows remote-mount flags
- LAN server startup time increases (loading agent dependencies)

**Phase to address:**
Project structure phase (before any feature implementation). Module boundaries must be established first.

---

### Pitfall 7: Mount TTL Expiry Race With Active Downloads

**What goes wrong:**
A mount has a 1-hour TTL. At minute 59, a browser user starts downloading a 4GB file that takes 10 minutes. At minute 60, the mount expires. The relay tears down the tunnel, killing the download at 90% completion. The user sees a broken download with no explanation.

**Why it happens:**
TTL expiry is implemented as a simple timer that kills the mount unconditionally. Developers test TTL with short-lived mounts and small files, so the expiry never interrupts an active transfer.

**How to avoid:**
- Track active transfers per mount. When TTL expires, stop accepting NEW requests but allow in-flight transfers to complete (grace period of 5-10 minutes).
- Alternatively, extend TTL automatically if active transfers exist, with a hard cap (e.g., TTL + 30 minutes maximum).
- Notify the agent when TTL is approaching (5 minutes warning) so the agent CLI can display a warning and offer to extend.
- Browser users should see the remaining mount TTL in the UI so they know not to start a huge download with 2 minutes remaining.

**Warning signs:**
- Downloads fail near mount expiry time
- No grace period logic in TTL cleanup
- No active transfer tracking on the relay
- Users report "random download failures" that correlate with mount duration

**Phase to address:**
Mount lifecycle phase. TTL cleanup must be aware of active transfers.

---

### Pitfall 8: JSON Encoding for Binary File Content Destroys Performance

**What goes wrong:**
The tunnel protocol uses JSON messages for everything, including file content. Binary file data must be Base64-encoded to fit in JSON, inflating payload size by 33%. A 100MB file becomes 133MB on the wire, and the CPU cost of Base64 encoding/decoding on both agent and relay adds significant latency. For large files, this can make the relay unusably slow compared to direct LAN transfer.

**Why it happens:**
The existing WebSocket infrastructure (`connection_manager.py`) uses `send_json()` / `receive_json()` exclusively. Developers extend this pattern to the tunnel protocol, sending file chunks as Base64 strings inside JSON objects. It works for small files and is easy to implement.

**How to avoid:**
- Use binary WebSocket frames (`send_bytes()` / `receive_bytes()`) for file content. Use a simple framing protocol: first N bytes are a header (request ID, chunk sequence number, flags), remaining bytes are raw file data.
- Use JSON text frames only for control messages (request initiation, directory listings, error responses, mount registration).
- Design the protocol to distinguish frame types: text frames = control/metadata, binary frames = file data. WebSocket natively supports both frame types on the same connection.
- Benchmark: on a typical cloud VM, Base64 encoding 256KB chunks costs ~0.5ms each. Over a 1GB file (4096 chunks), that is 2 seconds of pure encoding overhead per direction, plus 33% more network transfer.

**Warning signs:**
- All WebSocket messages use `send_json()` including file data
- File transfer throughput is significantly lower than expected network speed
- High CPU usage on relay during file transfers (Base64 encoding)
- Transfer speed test shows relay is 30%+ slower than direct connection

**Phase to address:**
Tunnel protocol design phase. Binary framing must be in the protocol spec from the start.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| JSON-only tunnel protocol (Base64 for files) | Simpler implementation, easier debugging | 33% bandwidth overhead, CPU cost, poor large-file performance | Never for file data -- use binary frames from day one |
| Single WebSocket per mount (no multiplexing) | Simpler relay logic | Head-of-line blocking: one slow download blocks other requests | Acceptable for v1.2 MVP if chunk-level interleaving is implemented. True multiplexing is v2 |
| In-memory mount registry on relay | No database dependency | Mounts lost on relay restart; cannot scale to multiple relay instances | Acceptable for v1.2 -- single-instance relay. Add Redis/persistent store in v2 |
| Relay stores mount passwords in memory | Simple, no external dependencies | Passwords lost on restart | Acceptable for v1.2 -- mount is ephemeral anyway |
| No agent authentication (rely on mount code secrecy) | Faster implementation | Any agent can claim a mount code; mount hijacking possible | Never -- agent must authenticate with a secret token when registering a mount |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Relay + existing auth middleware | Applying v1.1's cookie-based auth middleware to relay routes; browsers accessing mounts are NOT authenticated via the LAN server's session | Relay has its own auth: mount code + optional per-mount password. Do NOT reuse `AuthMiddleware` from v1.1 |
| Agent + existing ConnectionManager | Reusing the LAN server's `ConnectionManager` singleton for the tunnel WebSocket | Agent tunnel is a client-side WebSocket (connecting outbound). LAN `ConnectionManager` is server-side (accepting inbound). Different classes, different lifecycle |
| Agent + existing file_service | Agent calls `file_service.list_directory()` etc. but `file_service` depends on `get_server_config()` global | Agent must set its own `ServerConfig` with the mounted directory. Verify `set_server_config()` is called before any file operations in agent mode |
| Relay + Starlette static files | Relay's mount landing page conflicts with SPA catch-all `/{path:path}` route | Relay is a separate application/deployment. If co-hosted (dev mode), mount routes must be registered before the SPA catch-all |
| Browser + CORS on relay | Relay serves mount pages to browsers; if mount UI is a separate SPA, CORS blocks API calls | Serve mount UI from the relay origin. Same-origin eliminates CORS issues entirely |
| Agent CLI + existing CLI | `wfs mount` vs `wfs share` use the same `cli.py` argparse setup; conflicting flags | Use argparse subcommands. `share` and `mount` are separate subcommands with independent flag sets |
| Relay + WebSocket ping/pong | Relying on TCP keepalive to detect dead agent connections; cloud load balancers and proxies drop idle WebSockets after 60-120 seconds | Implement application-level ping/pong at 30-second intervals. Do NOT rely on WebSocket protocol-level pings alone -- some proxies strip them |
| Mount password + existing bcrypt | Reusing bcrypt for mount passwords adds 100-300ms per password check due to intentional slowness | For per-mount passwords, bcrypt is fine (checked once per session). But do NOT check bcrypt on every proxied request -- issue a session cookie after first check |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Relay buffers entire file in memory before forwarding to browser | Memory usage proportional to total concurrent download size | Stream chunks directly from WebSocket to HTTP response. Never accumulate | 3+ concurrent large file downloads on a 512MB VM |
| Agent reads entire file into memory before sending over WebSocket | Agent OOM on large files | Use `aiofiles` to read in chunks (64KB-256KB). Send each chunk as a binary frame | Any file larger than available RAM |
| Relay creates new asyncio Task per proxied request without limit | Unbounded task creation; event loop starvation | Use `asyncio.Semaphore` to limit concurrent proxied requests per mount (e.g., 20) | 50+ concurrent requests to a single mount (browser tabs, download managers) |
| DNS resolution for relay URL on every agent reconnection | Reconnection delayed by DNS timeout when network is flaky | Cache DNS result; use IP directly after initial resolution | Agent on unstable WiFi with DNS server issues |
| Directory listing serialization for large directories | Agent serializes 10,000-file directory as JSON; relay buffers entire response | Paginate directory listings. Limit to 1000 entries per response with cursor | Mounting a directory with 10,000+ files |
| Heartbeat ping/pong on same event loop as file transfer | Large file transfer starves heartbeat processing; relay declares agent dead | Use a separate asyncio task for heartbeat that is not blocked by data transfer tasks | During sustained large file transfer at network capacity |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Mount code in URL path (`/mount/abc123/files/...`) | Code visible in browser history, server logs, referrer headers | Accept mount code via initial POST or cookie; subsequent requests use session token. Code appears in URL only on the landing page |
| No agent authentication on tunnel registration | Anyone who guesses/brute-forces a mount code can register as the agent, serving malicious files | Agent must present a cryptographic secret (generated at mount creation) when connecting the tunnel |
| Relay forwards agent's error tracebacks to browser | Internal path information, Python version, library versions leaked | Relay must sanitize all error responses. Return generic error messages; log details server-side only |
| No origin validation on relay WebSocket | Cross-site WebSocket hijacking: malicious page connects to relay and registers a fake agent | Validate `Origin` header on agent WebSocket handshake. Only accept connections from expected agent origins (or skip origin check and rely on secret token) |
| Mount code enumeration via timing | `404` for invalid code vs `401` for valid-but-password-protected code reveals which codes are active | Return identical response for invalid code and wrong password. Use constant-time comparison for codes |
| Agent exposes upload capability through tunnel without explicit opt-in | User mounts `~/Documents` for sharing; attacker uploads malware into their documents folder | Default mount mode is read-only. Require explicit `--allow-upload` flag on the agent CLI to enable writes through the tunnel |
| Relay trusts agent-provided file metadata (size, name, type) | Agent (or compromised agent) sends fake Content-Length, causing browser to allocate excessive memory | Relay should stream without trusting Content-Length. Let the browser handle chunked transfer encoding |
| No TLS on agent-relay WebSocket | File content transmitted in plaintext between agent and relay; interceptable by ISP/network observer | Use `wss://` (WebSocket over TLS). The relay must have a valid TLS certificate. This is non-negotiable for internet-facing relay |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Mount succeeds silently with no feedback | User runs `wfs mount ~/Downloads` and sees nothing -- is it working? | Display: mount code, relay URL, QR code, TTL remaining, connection status. Mirror the existing `wfs share` output style |
| Browser shows generic "error" when agent is disconnected | User cannot distinguish "mount expired" from "agent offline" from "wrong code" | Specific error states: "Mount not found" (invalid code), "Mount offline" (agent disconnected), "Mount expired" (TTL elapsed), "Connecting..." (agent reconnecting) |
| No indication of relay latency vs LAN speed | User expects LAN-like speed through the relay and thinks it is broken | Show transfer speed in the browser UI. Note "Remote mount via relay -- speed depends on internet connection" |
| Mount landing page requires entering code manually when QR was scanned | QR code contains the URL with mount code but landing page still asks for code input | QR URL should include the code in the path: `relay.example.com/m/abc123`. Landing page auto-navigates to mount when code is in URL |
| Agent disconnects with no option to reconnect manually | Laptop sleeps, agent drops. User must kill and restart the CLI | Agent should auto-reconnect. Display reconnection attempts in terminal. Provide manual reconnect command or keep-alive info |
| TTL expires with no warning | Mount suddenly stops working mid-session | Show countdown in agent CLI and browser UI. Warn at 5 minutes remaining. Offer "extend" option in agent CLI |

## "Looks Done But Isn't" Checklist

- [ ] **Tunnel protocol:** Two browser tabs downloading different files simultaneously receive correct file content (correlation IDs work)
- [ ] **Tunnel protocol:** 1GB+ file download completes without relay memory exceeding 100MB (backpressure works)
- [ ] **Tunnel protocol:** File download through tunnel has correct `Content-Type`, `Content-Length`, and `Content-Disposition` headers (not just raw bytes)
- [ ] **Reconnection:** Agent laptop sleeps for 5 minutes, wakes up, auto-reconnects, and browser users can resume browsing within 10 seconds
- [ ] **Reconnection:** In-flight downloads when agent disconnects return an error to the browser (not infinite spinner)
- [ ] **Reconnection:** Agent reconnects to the SAME mount code (does not create a new mount)
- [ ] **Mount lifecycle:** TTL expiry does not kill active downloads (grace period works)
- [ ] **Mount lifecycle:** Expired mount code returns 410 Gone, not 404 (prevents confusion with invalid codes)
- [ ] **Mount lifecycle:** Agent CLI displays time remaining and warns before expiry
- [ ] **Security:** Rate limiting on mount code lookup prevents brute force (>5 failures per minute per IP returns 429)
- [ ] **Security:** Agent authenticates with secret token, not just mount code
- [ ] **Security:** Default mount mode is read-only (no uploads through tunnel unless `--allow-upload`)
- [ ] **Security:** Path traversal via tunnel returns 400, not a file from outside shared directory
- [ ] **Security:** Relay uses `wss://` (TLS) for agent connections
- [ ] **LAN preservation:** `wfs share ~/Downloads` works identically to v1.1 with no new dependencies loaded
- [ ] **LAN preservation:** All existing tests pass without modification
- [ ] **LAN preservation:** `--help` output for `wfs share` is unchanged
- [ ] **Performance:** Directory listing for 1000-file directory returns in under 2 seconds through tunnel
- [ ] **Performance:** Concurrent downloads (5 users, 100MB each) complete without relay OOM

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| No backpressure (OOM on relay) | HIGH | Requires redesigning the data flow pipeline between WebSocket and HTTP response. Cannot be patched onto a buffering design |
| Missing correlation IDs | HIGH | Requires rewriting the tunnel protocol wire format. Every message format changes |
| JSON-encoded file data | MEDIUM | Switch `send_json` to `send_bytes` for data frames. Keep JSON for control. Requires protocol version bump |
| Agent reconnection drops requests | MEDIUM | Add Future cleanup on disconnect. Moderate refactor of relay's request tracking |
| Mount code brute force | LOW | Add rate limiting middleware. No protocol changes needed |
| LAN mode regression | LOW | Revert imports, fix module boundaries. Tests catch this immediately |
| TTL kills active downloads | LOW | Add grace period check before teardown. Small code change in lifecycle manager |
| Missing agent authentication | MEDIUM | Add secret token field to mount registration. Requires coordinating agent + relay changes |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| No backpressure (OOM) | Tunnel protocol design | Load test: 5 concurrent 500MB downloads, relay RSS stays under 200MB |
| Missing correlation IDs | Tunnel protocol design | Test: 10 parallel requests return correct responses (content hash comparison) |
| JSON file encoding overhead | Tunnel protocol design | Benchmark: tunnel transfer speed within 80% of direct HTTP transfer speed |
| Agent reconnection drops requests | Tunnel protocol + relay implementation | Test: kill agent WebSocket mid-download, browser gets 502 within 5 seconds |
| Mount code brute force | Relay implementation | Test: 6th invalid code attempt within 60s returns 429 |
| Open proxy / path traversal | Tunnel protocol design + agent implementation | Test: `../../../etc/passwd` through tunnel returns 400 |
| LAN mode regression | Project structure (first phase) | Existing test suite passes with zero modifications |
| TTL kills active downloads | Mount lifecycle implementation | Test: start download at TTL-30s, verify download completes |
| Agent authentication missing | Relay + agent implementation | Test: agent with wrong secret gets WebSocket close code 4003 |
| Binary framing vs JSON | Tunnel protocol design | Code review: `send_bytes()` used for file data, `send_json()` only for control |

## Sources

- Direct codebase analysis: `server/app/services/connection_manager.py` (singleton `manager`, `send_json()`-only API), `server/app/routers/websocket.py` (auth check pattern, message routing), `server/app/config.py` (global `ServerConfig` pattern), `server/app/main.py` (SPA catch-all, CORS config)
- Direct codebase analysis: `server/app/services/file_service.py` (`resolve_safe_path()` validation pattern)
- [WebSocket Backpressure in Streams](https://skylinecodes.substack.com/p/backpressure-in-websocket-streams) -- backpressure is not built into WebSocket; must be implemented at application layer
- [Managing WebSocket Backpressure in FastAPI](https://hexshift.medium.com/managing-websocket-backpressure-in-fastapi-applications-893c049017d4) -- asyncio.Queue-based flow control pattern
- [websockets library memory docs](https://websockets.readthedocs.io/en/stable/topics/memory.html) -- buffer sizing, max_size, max_queue parameters
- [WSP - HTTP tunnel over WebSocket](https://github.com/root-gg/wsp) -- request-response correlation with UUID and timeout protection
- [Reverse Proxying over WebSockets (Codemancers)](https://www.codemancers.com/blog/reverse-proxying-over-websockets) -- multiplexing, dynamic port allocation failures, WebSocket relay architecture
- [How I built Ngrok Alternative](https://dev.to/azimjohn/how-i-built-ngrok-alternative-3n0g) -- JSON encoding mistake for binary data, Base64 overhead
- [Building an HTTP Tunnel with WebSocket](https://dzone.com/articles/building-a-http-tunnel-with-websocket-and-nodejs) -- tunnel protocol design patterns
- [OWASP WebSocket Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/WebSocket_Security_Cheat_Sheet.html) -- origin validation, authentication, rate limiting
- [Cross-site WebSocket Hijacking (PortSwigger)](https://portswigger.net/web-security/websockets/cross-site-websocket-hijacking) -- CSWSH attack vector
- [WebSocket Reconnect Strategies](https://apidog.com/blog/websocket-reconnect/) -- exponential backoff, jitter, max retry limits
- [websockets keepalive docs](https://websockets.readthedocs.io/en/stable/topics/keepalive.html) -- ping/pong intervals, proxy timeout interaction
- [Challenges of Scaling WebSockets](https://dev.to/ably/challenges-of-scaling-websockets-3493) -- connection lifecycle, stale connection cleanup

---
*Pitfalls research for: WiFi File Server v1.2 remote mounts relay + agent*
*Researched: 2026-03-11*
