# Roadmap: Network File Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-03-09)
- ✅ **v1.1 Share & Access Control** — Phases 5-7 (shipped 2026-03-11)
- ✅ **v1.2 Remote Mounts** — Phases 8-11 (shipped 2026-03-16)
- 🚧 **v1.3 Productionize Friend Tier** — Phases 12-16 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-03-09</summary>

- [x] Phase 1: Foundation and Discovery (3/3 plans) — completed 2026-03-08
- [x] Phase 2: File Management (4/4 plans) — completed 2026-03-09
- [x] Phase 3: Search, Preview, and UI Polish (3/3 plans) — completed 2026-03-09
- [x] Phase 4: Real-Time Features (3/3 plans) — completed 2026-03-09

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Share & Access Control (Phases 5-7) — SHIPPED 2026-03-11</summary>

- [x] Phase 5: Access Control (3/3 plans) — completed 2026-03-09
- [x] Phase 6: Expiring Share Links (2/2 plans) — completed 2026-03-09
- [x] Phase 7: Device Discovery (2/2 plans) — completed 2026-03-09

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Remote Mounts (Phases 8-11) — SHIPPED 2026-03-16</summary>

- [x] Phase 8: Tunnel Protocol (2/2 plans) — completed 2026-03-11
- [x] Phase 9: Relay Server (2/2 plans) — completed 2026-03-11
- [x] Phase 10: Agent CLI (2/2 plans) — completed 2026-03-11
- [x] Phase 11: Remote Access and Hardening (5/5 plans) — completed 2026-03-16

Full details: `.planning/milestones/v1.2-ROADMAP.md`

</details>

### 🚧 v1.3 Productionize Friend Tier (In Progress)

**Milestone Goal:** Deploy the relay to Google Cloud Run and harden it for real-world use — Dockerized, secured, with persistent state, a default public drop box, and auto-expiring file uploads.

- [x] **Phase 12: Cloud Run Foundation** - Dockerize the relay, add health check and structured logging, fix HTTPS cookie/CORS/proxy-header security bugs (completed 2026-03-16)
- [x] **Phase 13: Abuse Prevention** - Rate-limit mount registration and proxy requests, enforce max TTL and per-IP mount cap (completed 2026-03-17)
- [x] **Phase 14: Persistent Mount Registry** - SQLite mount metadata store survives relay restarts; agents reclaim codes on reconnect (completed 2026-03-30)
- [x] **Phase 15: UX Polish and Drop Box** - Landing page with OG tags, connection status overlays, always-on drop box, per-file upload TTL (completed 2026-04-03)
- [ ] **Phase 16: Wire File TTL Notifications & Expired Files Handler** - Fix broadcast_fn wiring for TTL toast, add tunnel handlers for agent keep/delete responses (gap closure)

Full details: `.planning/milestones/v1.3-ROADMAP.md`

### Phase 16: Wire File TTL Notifications & Expired Files Handler
**Goal**: File TTL auto-deletion sends WebSocket toast notifications to connected browsers, and the relay correctly processes agent responses to expired-files prompts on mount restart.
**Depends on**: Phase 15
**Requirements**: FTTL-04, FTTL-06

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation and Discovery | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. File Management | v1.0 | 4/4 | Complete | 2026-03-09 |
| 3. Search, Preview, and UI Polish | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Real-Time Features | v1.0 | 3/3 | Complete | 2026-03-09 |
| 5. Access Control | v1.1 | 3/3 | Complete | 2026-03-09 |
| 6. Expiring Share Links | v1.1 | 2/2 | Complete | 2026-03-09 |
| 7. Device Discovery | v1.1 | 2/2 | Complete | 2026-03-09 |
| 8. Tunnel Protocol | v1.2 | 2/2 | Complete | 2026-03-11 |
| 9. Relay Server | v1.2 | 2/2 | Complete | 2026-03-11 |
| 10. Agent CLI | v1.2 | 2/2 | Complete | 2026-03-11 |
| 11. Remote Access and Hardening | v1.2 | 5/5 | Complete | 2026-03-16 |
| 12. Cloud Run Foundation | 2/2 | Complete    | 2026-03-16 | - |
| 13. Abuse Prevention | 2/2 | Complete    | 2026-03-17 | - |
| 14. Persistent Mount Registry | v1.3 | Complete    | 2026-03-30 | - |
| 15. UX Polish and Drop Box | v1.3 | 4/4 | Complete | 2026-04-03 |
| 16. Wire File TTL Notifications & Expired Files Handler | v1.3 | 0/1 | Pending | - |
