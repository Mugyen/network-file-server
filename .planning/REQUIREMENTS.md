# Requirements: WiFi File Server v1.1

**Defined:** 2026-03-10
**Core Value:** Any device on the same WiFi network can instantly share files with zero setup — scan QR, drop files, done.

## v1.1 Requirements

Requirements for Share & Access Control milestone. Each maps to roadmap phases.

### Access Control

- [ ] **AUTH-01**: User can set a server-wide password via `--password` CLI flag
- [ ] **AUTH-02**: User sees a full-page login form when accessing a password-protected server
- [ ] **AUTH-03**: User receives a session cookie on correct password, granting access until browser close or server restart
- [ ] **AUTH-04**: User can start server in read-only mode via `--read-only` CLI flag, blocking all write operations
- [ ] **AUTH-05**: User sees write controls (upload, delete, rename, create folder) hidden in read-only mode
- [ ] **AUTH-06**: User can start server in receive mode via `--receive` CLI flag, showing upload-only interface
- [ ] **AUTH-07**: User sees a minimal drop box UI with only drag-and-drop upload, file picker, and progress in receive mode
- [ ] **AUTH-08**: CLI rejects mutually exclusive `--read-only --receive` with a clear error

### Sharing

- [ ] **SHARE-01**: User can generate an expiring share link for any file via a "Share" action
- [ ] **SHARE-02**: User can select a TTL when creating a share link (15min, 1hr, 6hr, 24hr)
- [ ] **SHARE-03**: Link recipient sees a clean download page with file name, size, and download button
- [ ] **SHARE-04**: Link recipient sees a clear "link expired" page when accessing an expired link
- [ ] **SHARE-05**: Share links bypass password protection (the token is the authentication)
- [ ] **SHARE-06**: Server operator can list all active share links
- [ ] **SHARE-07**: Server operator can revoke any active share link

### Device Discovery

- [ ] **DISC-01**: User can view a panel showing all connected devices with name, IP, and connection duration
- [ ] **DISC-02**: User sees device type icons (phone/laptop/tablet) parsed from User-Agent
- [ ] **DISC-03**: User sees real-time updates when devices connect or disconnect
- [ ] **DISC-04**: User sees a "You" indicator for their own device in the device list

## Future Requirements

### Server UX (Deferred to v1.2)

- **TUI-01**: Server operator sees a Rich terminal dashboard with QR, devices, activity, stats
- **TUI-02**: Server operator can disable TUI via `--no-tui` flag
- **SPEED-01**: User can run a built-in LAN speed test (download/upload Mbps + latency)

### Advanced Sharing (Deferred to v2+)

- **SHARE-08**: Share links with max download count (expire after N downloads)
- **SHARE-09**: Password-protected share links (separate from server password)
- **RECV-01**: Custom welcome message for drop box page
- **RECV-02**: Auto-organize uploads by uploader name or timestamp subdirectories

### Network Discovery (Deferred to v2+)

- **DISC-05**: mDNS/Bonjour broadcast so server appears in network discovery
- **DISC-06**: Auto-discover other WiFi File Server instances on the network

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-user accounts / multi-password | Turns simple LAN tool into IAM system. Contradicts "zero setup" core value. |
| HTTPS / TLS | Certificate management is massive friction for LAN tool. Password protects against casual access, not sniffing. |
| Persistent share links (survive restart) | Requires database. In-memory is a feature — no stale links. |
| Full Textual TUI framework | Event loop conflicts with uvicorn. Rich `Live` is the correct lighter alternative. |
| Rate limiting on password | LAN requires physical network proximity. bcrypt work factor is sufficient. |
| File-level permissions / ACLs | Way beyond v1.1 scope. Server-wide mode covers use cases. |
| Custom upload forms for drop box | Scope creep. Optional uploader name only. |
| mDNS server discovery | Platform-specific behavior, firewall issues. QR code is already zero-friction. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | — | Pending |
| AUTH-02 | — | Pending |
| AUTH-03 | — | Pending |
| AUTH-04 | — | Pending |
| AUTH-05 | — | Pending |
| AUTH-06 | — | Pending |
| AUTH-07 | — | Pending |
| AUTH-08 | — | Pending |
| SHARE-01 | — | Pending |
| SHARE-02 | — | Pending |
| SHARE-03 | — | Pending |
| SHARE-04 | — | Pending |
| SHARE-05 | — | Pending |
| SHARE-06 | — | Pending |
| SHARE-07 | — | Pending |
| DISC-01 | — | Pending |
| DISC-02 | — | Pending |
| DISC-03 | — | Pending |
| DISC-04 | — | Pending |

**Coverage:**
- v1.1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after initial definition*
