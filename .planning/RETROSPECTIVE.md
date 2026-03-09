# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-09
**Phases:** 4 | **Plans:** 13 | **Tasks:** ~29

### What Was Built
- FastAPI backend with path traversal guard, file management, search, preview, and WebSocket infrastructure
- React + Tailwind CSS v4 SPA with file browser, upload, preview modal, dark mode, clipboard, file requests
- QR code discovery (ASCII terminal + SVG web) for zero-setup device connection
- Real-time collaboration: toast notifications, shared clipboard scratchpad, file request system

### What Worked
- Coarse granularity (4 phases instead of 7) kept overhead low and momentum high
- TDD on backend plans (RED tests before GREEN implementation) caught path traversal edge cases early
- Shared WebSocket ConnectionManager made Phase 4 features (notifications, clipboard, requests) composable
- Consistent service/router/schema layering on backend made each plan predictable
- Average plan execution ~5min — tight feedback loops

### What Was Inefficient
- Phase 1 plan checkboxes in ROADMAP.md were never updated to [x] (cosmetic, but inconsistent with Phases 2-4)
- Some summary-extract fields (one_liner) were not populated in SUMMARY.md files — tooling gap
- Velocity tracking only covered Phases 1-3 in STATE.md; Phase 4 metrics were appended separately

### Patterns Established
- XHR for upload progress (fetch lacks upload.onprogress)
- useRef for WebSocket instances and drag counters to avoid stale closures
- Native URLSearchParams + pushState for simple path navigation (no React Router)
- Tailwind v4 @custom-variant for dark mode with FOUC prevention inline script
- JSON file persistence for clipboard/requests data (simple, no database needed for LAN tool)
- Device identity via random adjective+animal names in localStorage

### Key Lessons
1. Starlette's FileResponse handles Range requests natively — no custom 206 streaming needed
2. PrismLight with individual language imports keeps bundle size manageable for syntax highlighting
3. Textarea-based scratchpad is the correct approach for HTTP LAN tools (Clipboard API needs HTTPS)
4. ConflictDialog should force user choice (overwrite/rename/skip) with no cancel — prevents ambiguous state

### Cost Observations
- Model mix: balanced profile (opus for planning/research, sonnet for execution)
- Sessions: ~4 sessions across 1 day
- Notable: entire v1.0 MVP built in ~1.1 hours of execution time

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~4 | 4 | Initial release — coarse granularity, TDD backend, rapid frontend |

### Top Lessons (Verified Across Milestones)

1. Coarse phase granularity (fewer, larger phases) reduces planning overhead without sacrificing quality
2. TDD on API endpoints catches edge cases early and provides confidence for frontend integration
