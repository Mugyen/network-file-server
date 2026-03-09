# Roadmap: WiFi File Server

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-4 (shipped 2026-03-09)
- **v1.1 Share & Access Control** -- Phases 5-7 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-4) -- SHIPPED 2026-03-09</summary>

- [x] Phase 1: Foundation and Discovery (3/3 plans) -- completed 2026-03-08
- [x] Phase 2: File Management (4/4 plans) -- completed 2026-03-09
- [x] Phase 3: Search, Preview, and UI Polish (3/3 plans) -- completed 2026-03-09
- [x] Phase 4: Real-Time Features (3/3 plans) -- completed 2026-03-09

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### v1.1 Share & Access Control (In Progress)

**Milestone Goal:** Add access control (password, read-only, receive mode), expiring share links, and device discovery to the WiFi File Server.

- [ ] **Phase 5: Access Control** - Password protection, read-only mode, receive mode, and CLI validation for server access modes
- [ ] **Phase 6: Expiring Share Links** - Generate, distribute, and manage time-limited share links for files
- [ ] **Phase 7: Device Discovery** - Real-time panel showing connected devices with type, status, and self-identification

## Phase Details

### Phase 5: Access Control
**Goal**: Server operator can restrict access and write operations via CLI flags, and clients see the appropriate gated or limited UI
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08
**Success Criteria** (what must be TRUE):
  1. User starting server with `--password secret` sees a login form on first visit, and after entering the correct password, browses files normally with a persistent session
  2. User starting server with `--read-only` can browse and download files but sees no upload, delete, rename, or create-folder controls, and direct API write attempts are rejected
  3. User starting server with `--receive` sees only a minimal drop-box interface with drag-and-drop upload, file picker, and progress -- no file listing or navigation
  4. User starting server with `--read-only --receive` sees a clear CLI error and the server does not start
  5. User accessing a password-protected server from a second browser must authenticate independently
**Plans:** 3 plans

Plans:
- [ ] 05-01-PLAN.md -- CLI flags, config extension, auth service (backend foundation)
- [ ] 05-02-PLAN.md -- Auth middleware, route guards, server-info extension (backend enforcement)
- [ ] 05-03-PLAN.md -- Login page, drop box page, mode badges, read-only UI (frontend)

### Phase 6: Expiring Share Links
**Goal**: Users can generate temporary, self-expiring links to share specific files, and recipients can download without needing server access
**Depends on**: Phase 5 (middleware and auth patterns established)
**Requirements**: SHARE-01, SHARE-02, SHARE-03, SHARE-04, SHARE-05, SHARE-06, SHARE-07
**Success Criteria** (what must be TRUE):
  1. User right-clicks or clicks "Share" on any file and receives a URL with a chosen TTL (15min, 1hr, 6hr, 24hr) that they can copy
  2. Recipient opening a valid share link sees a clean download page with file name, size, and a download button -- no server login required even if password protection is enabled
  3. Recipient opening an expired share link sees a clear "link expired" message instead of a download
  4. Server operator can list all active share links and revoke any of them, immediately invalidating the link
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: Device Discovery
**Goal**: Users can see who is connected to the server in real time, identify their own device, and observe connect/disconnect events live
**Depends on**: Phase 5 (WebSocket auth/session patterns established)
**Requirements**: DISC-01, DISC-02, DISC-03, DISC-04
**Success Criteria** (what must be TRUE):
  1. User sees a "Devices" panel listing all currently connected clients with device name, IP address, and how long they have been connected
  2. User sees device-type icons (phone, laptop, tablet) derived from each client's User-Agent
  3. User sees devices appear and disappear in real time as clients connect and disconnect, without refreshing
  4. User sees a "You" badge next to their own device in the list
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6 -> 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation and Discovery | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. File Management | v1.0 | 4/4 | Complete | 2026-03-09 |
| 3. Search, Preview, and UI Polish | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Real-Time Features | v1.0 | 3/3 | Complete | 2026-03-09 |
| 5. Access Control | v1.1 | 0/3 | Planned | - |
| 6. Expiring Share Links | v1.1 | 0/? | Not started | - |
| 7. Device Discovery | v1.1 | 0/? | Not started | - |
