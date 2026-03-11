# Roadmap: WiFi File Server

## Milestones

- v1.0 MVP -- Phases 1-4 (shipped 2026-03-09)
- v1.1 Share & Access Control -- Phases 5-7 (shipped 2026-03-11)
- v1.2 Remote Mounts -- Phases 8-11 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) -- SHIPPED 2026-03-09</summary>

- [x] Phase 1: Foundation and Discovery (3/3 plans) -- completed 2026-03-08
- [x] Phase 2: File Management (4/4 plans) -- completed 2026-03-09
- [x] Phase 3: Search, Preview, and UI Polish (3/3 plans) -- completed 2026-03-09
- [x] Phase 4: Real-Time Features (3/3 plans) -- completed 2026-03-09

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>v1.1 Share & Access Control (Phases 5-7) -- SHIPPED 2026-03-11</summary>

- [x] Phase 5: Access Control (3/3 plans) -- completed 2026-03-09
- [x] Phase 6: Expiring Share Links (2/2 plans) -- completed 2026-03-09
- [x] Phase 7: Device Discovery (2/2 plans) -- completed 2026-03-09

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### v1.2 Remote Mounts (In Progress)

**Milestone Goal:** Enable file sharing over the internet by letting users mount their local filesystem through a public relay server, accessible via short code or QR -- without requiring recipients to install anything.

- [ ] **Phase 8: Tunnel Protocol** - Binary WebSocket framing with multiplexing, correlation IDs, and backpressure
- [ ] **Phase 9: Relay Server** - Public FastAPI server that routes browser requests to agents by mount code
- [ ] **Phase 10: Agent CLI** - CLI command to mount a local directory through the relay server
- [ ] **Phase 11: Remote Access and Hardening** - Password protection, TTL expiry, and SPA adaptation for remote mounts

## Phase Details

### Phase 8: Tunnel Protocol
**Goal**: A shared protocol library enables binary-framed, multiplexed communication between relay and agent over a single WebSocket connection
**Depends on**: Nothing (v1.2 foundation)
**Requirements**: TUNL-01, TUNL-02, TUNL-03, TUNL-04
**Success Criteria** (what must be TRUE):
  1. Binary frames with 21-byte headers (type, request_id, payload_length) can be serialized and deserialized correctly in both directions
  2. Multiple concurrent requests are multiplexed over a single WebSocket with UUID correlation, and responses arrive at the correct caller
  3. Backpressure via bounded asyncio.Queue prevents memory exhaustion when streaming large files through the tunnel
  4. Control messages (mount registration, heartbeat, error) use JSON text frames and are distinguishable from binary data frames
**Plans**: 2 plans

Plans:
- [ ] 08-01-PLAN.md — Frame primitives: constants, enums, exceptions, serialization, WebSocket protocol interface
- [ ] 08-02-PLAN.md — TunnelConnection: stream multiplexing, backpressure, heartbeat, first-byte timeout

### Phase 9: Relay Server
**Goal**: A public-facing relay server accepts agent connections, routes browser HTTP requests through the tunnel to the correct agent, and handles mount lifecycle
**Depends on**: Phase 8
**Requirements**: RELY-01, RELY-02, RELY-03, RELY-04
**Success Criteria** (what must be TRUE):
  1. Relay maintains an in-memory mount registry and correctly routes browser requests at `/m/{code}/*` to the agent that registered that mount code
  2. Mount landing page allows a user to enter a mount code or scan a QR code and be redirected to the mounted file browser
  3. When a mount is offline, expired, or not found, the user sees a clear error page explaining the situation (not a generic 500)
  4. Relay runs as a separate FastAPI application that can be deployed independently from the LAN server
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

### Phase 10: Agent CLI
**Goal**: Users can mount a local directory through the relay server with a single CLI command, making their files accessible to anyone with the mount code
**Depends on**: Phase 9
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04
**Success Criteria** (what must be TRUE):
  1. User can run `wifi-file-server mount ./files --server <url>` and the agent connects to the relay, registers a mount code, and begins serving files through the tunnel
  2. Agent starts a local FastAPI server using `create_app()` and proxies tunneled requests to it, so all v1.0/v1.1 features (preview, search, clipboard, drag-drop) work identically in remote mode
  3. Agent displays the mount URL and a scannable QR code in the terminal after successful connection
  4. When the WebSocket connection drops, the agent auto-reconnects with exponential backoff and jitter without user intervention
**Plans**: TBD

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD

### Phase 11: Remote Access and Hardening
**Goal**: Remote mounts support password protection, auto-expiry, and the React SPA works seamlessly through the relay proxy
**Depends on**: Phase 10
**Requirements**: ACCS-01, ACCS-02, RMUI-01, RMUI-02
**Success Criteria** (what must be TRUE):
  1. Mount owner can set a password via `--password` flag and remote users must authenticate before accessing files (reusing v1.1 auth flow transparently through the tunnel)
  2. Mount auto-expires after the TTL duration specified via `--ttl` flag, and expired mounts show a clear "expired" page to visitors
  3. React SPA detects remote mount context and prefixes all API calls with `/m/{code}`, so file browsing, upload, download, and preview work through the relay
  4. Real-time WebSocket features (clipboard sync, transfer notifications, device discovery) function through the relay tunnel
**Plans**: TBD

Plans:
- [ ] 11-01: TBD
- [ ] 11-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 8 -> 9 -> 10 -> 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation and Discovery | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. File Management | v1.0 | 4/4 | Complete | 2026-03-09 |
| 3. Search, Preview, and UI Polish | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Real-Time Features | v1.0 | 3/3 | Complete | 2026-03-09 |
| 5. Access Control | v1.1 | 3/3 | Complete | 2026-03-09 |
| 6. Expiring Share Links | v1.1 | 2/2 | Complete | 2026-03-09 |
| 7. Device Discovery | v1.1 | 2/2 | Complete | 2026-03-09 |
| 8. Tunnel Protocol | v1.2 | 0/2 | Planning | - |
| 9. Relay Server | v1.2 | 0/? | Not started | - |
| 10. Agent CLI | v1.2 | 0/? | Not started | - |
| 11. Remote Access and Hardening | v1.2 | 0/? | Not started | - |
