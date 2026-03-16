# Roadmap: Network File Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-03-09)
- ✅ **v1.1 Share & Access Control** — Phases 5-7 (shipped 2026-03-11)
- ✅ **v1.2 Remote Mounts** — Phases 8-11 (shipped 2026-03-16)
- 🚧 **v1.3 Productionize Friend Tier** — Phases 12-15 (in progress)

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

- [ ] **Phase 12: Cloud Run Foundation** - Dockerize the relay, add health check and structured logging, fix HTTPS cookie/CORS/proxy-header security bugs
- [ ] **Phase 13: Abuse Prevention** - Rate-limit mount registration and proxy requests, enforce max TTL and per-IP mount cap
- [ ] **Phase 14: Persistent Mount Registry** - SQLite mount metadata store survives relay restarts; agents reclaim codes on reconnect
- [ ] **Phase 15: UX Polish and Drop Box** - Landing page with OG tags, connection status overlays, always-on drop box, per-file upload TTL

Full details: `.planning/milestones/v1.3-ROADMAP.md`

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
| 12. Cloud Run Foundation | v1.3 | 0/2 | Not started | - |
| 13. Abuse Prevention | v1.3 | 0/1 | Not started | - |
| 14. Persistent Mount Registry | v1.3 | 0/1 | Not started | - |
| 15. UX Polish and Drop Box | v1.3 | 0/4 | Not started | - |
