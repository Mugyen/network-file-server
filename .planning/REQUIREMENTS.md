# Requirements: WiFi File Server

**Defined:** 2026-03-11
**Core Value:** Any device on the same WiFi network can instantly share files with zero setup — scan QR, drop files, done.

## v1.2 Requirements

Requirements for Remote Mounts milestone. Each maps to roadmap phases.

### Tunnel Protocol

- [ ] **TUNL-01**: Agent and relay communicate via binary WebSocket frames with 9-byte headers (type, request_id, payload_length)
- [ ] **TUNL-02**: Concurrent browser requests are multiplexed over a single agent WebSocket using correlation IDs
- [ ] **TUNL-03**: Relay enforces backpressure via bounded asyncio.Queue to prevent OOM during large transfers
- [ ] **TUNL-04**: Control messages (mount registration, heartbeat, errors) use JSON text frames

### Relay Server

- [ ] **RELY-01**: Relay server maintains in-memory mount registry mapping codes to agent WebSocket connections
- [ ] **RELY-02**: Browser HTTP requests to `/m/{code}/*` are proxied through the tunnel to the correct agent
- [ ] **RELY-03**: Mount landing page allows users to enter a code or scan QR to access a mount
- [ ] **RELY-04**: Clean error pages display when a mount is offline, expired, or not found

### Agent CLI

- [ ] **AGNT-01**: User can mount a local directory via `wifi-file-server mount ./files --server <url>`
- [ ] **AGNT-02**: Agent starts local FastAPI server using `create_app()` and proxies tunneled requests via httpx
- [ ] **AGNT-03**: Agent displays mount URL and QR code in terminal after successful connection
- [ ] **AGNT-04**: Agent auto-reconnects on WebSocket drop with exponential backoff and jitter

### Access Control

- [ ] **ACCS-01**: Mount owner can set a password via `--password` flag, reusing v1.1 auth at mount level
- [ ] **ACCS-02**: Mount auto-expires after TTL duration via `--ttl` flag

### Remote UI

- [ ] **RMUI-01**: React SPA detects remote mount context and prefixes API calls with `/m/{code}`
- [ ] **RMUI-02**: Real-time WebSocket features (clipboard, notifications, device discovery) work through relay tunnel

## Future Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### User Accounts (v1.3+)

- **ACCT-01**: User can register and login with email and password
- **ACCT-02**: User gets isolated file storage with quota
- **ACCT-03**: User can manage their own mounts persistently
- **ACCT-04**: Device allowlists per mount
- **ACCT-05**: Role-based permissions per mount (read/write/receive per device)

### Advanced Relay (v1.3+)

- **ADVR-01**: Rate limiting on mount code lookups (brute force protection)
- **ADVR-02**: Mount code preservation across agent reconnects (grace period)
- **ADVR-03**: Relay admin status dashboard
- **ADVR-04**: Custom mount codes / vanity URLs

## Out of Scope

| Feature | Reason |
|---------|--------|
| E2E encryption | High complexity, deferred to v2+ |
| WebRTC P2P transfers | Different architecture entirely |
| Server-side file caching | Pure proxy model — no server storage |
| Containerization / K8S | Keep deployment simple for now |
| Custom domains per mount | DNS/TLS complexity, v1.3+ |
| Persistent mounts (survive restart) | In-memory registry is simpler and safer |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TUNL-01 | — | Pending |
| TUNL-02 | — | Pending |
| TUNL-03 | — | Pending |
| TUNL-04 | — | Pending |
| RELY-01 | — | Pending |
| RELY-02 | — | Pending |
| RELY-03 | — | Pending |
| RELY-04 | — | Pending |
| AGNT-01 | — | Pending |
| AGNT-02 | — | Pending |
| AGNT-03 | — | Pending |
| AGNT-04 | — | Pending |
| ACCS-01 | — | Pending |
| ACCS-02 | — | Pending |
| RMUI-01 | — | Pending |
| RMUI-02 | — | Pending |

**Coverage:**
- v1.2 requirements: 16 total
- Mapped to phases: 0
- Unmapped: 16 ⚠️

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after initial definition*
