# Requirements: WiFi File Server

**Defined:** 2026-03-09
**Core Value:** Any device on the same WiFi network can instantly share files with zero setup -- scan QR, drop files, done.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [ ] **FOUND-01**: Server starts with FastAPI backend serving React SPA
- [ ] **FOUND-02**: CLI accepts folder path argument and optional port
- [ ] **FOUND-03**: Path traversal protection on all file operations
- [ ] **FOUND-04**: CORS configured for development (Vite proxy)

### File Management

- [ ] **FILE-01**: User can browse files in the shared folder
- [ ] **FILE-02**: User can navigate into subdirectories with breadcrumb trail
- [ ] **FILE-03**: User can upload multiple files via drag-and-drop with individual progress bars
- [ ] **FILE-04**: User can download individual files
- [ ] **FILE-05**: User can select multiple files and download as ZIP
- [ ] **FILE-06**: User can delete files with confirmation dialog
- [ ] **FILE-07**: User can rename files inline
- [ ] **FILE-08**: User can create new folders
- [ ] **FILE-09**: User can batch delete selected files

### Discovery

- [ ] **DISC-01**: QR code displayed in terminal on server start (ASCII)
- [ ] **DISC-02**: QR code displayed on web UI (SVG)
- [ ] **DISC-03**: Local IP address auto-detected and displayed

### Search & Filter

- [ ] **SRCH-01**: User can search files by name (instant client-side filtering)
- [ ] **SRCH-02**: User can filter by file type category (images, videos, docs, audio, archives, code)
- [ ] **SRCH-03**: User can sort by name, size, date modified, type

### Media Preview

- [ ] **MEDP-01**: User can preview images in a lightbox with zoom
- [ ] **MEDP-02**: User can stream video/audio in-browser with seeking
- [ ] **MEDP-03**: User can view PDFs in embedded viewer
- [ ] **MEDP-04**: User can view code files with syntax highlighting
- [ ] **MEDP-05**: User can view markdown files rendered as HTML

### Real-Time

- [ ] **RTME-01**: WebSocket connection established on page load
- [ ] **RTME-02**: Toast notifications shown for file uploads/downloads
- [ ] **RTME-03**: Shared text clipboard (scratchpad) synced across all connected devices
- [ ] **RTME-04**: User can create a file request with description visible to all devices
- [ ] **RTME-05**: User can fulfill a file request by uploading

### UI/UX

- [ ] **UIUX-01**: Dark mode with system preference detection and manual toggle
- [ ] **UIUX-02**: Responsive layout works on mobile devices
- [ ] **UIUX-03**: File type icons displayed for all files

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Security

- **SEC-01**: E2E encrypted file transfers (Web Crypto API + PIN-derived key)
- **SEC-02**: Session PIN authentication displayed in terminal
- **SEC-03**: HTTPS via self-signed cert generation

### Clipboard (Advanced)

- **CLIP-01**: Clipboard history (last N items)
- **CLIP-02**: Auto-detect URLs and make clickable
- **CLIP-03**: Auto-detect code and apply syntax highlighting
- **CLIP-04**: Browser Clipboard API integration (HTTPS only)

### File Requests (Advanced)

- **FREQ-01**: Request status tracking (pending, fulfilled, expired)
- **FREQ-02**: Request auto-expire after configurable timeout
- **FREQ-03**: Fulfillment notification to requester

### Notifications (Advanced)

- **NOTF-01**: Browser Push Notification API integration
- **NOTF-02**: Notification history panel
- **NOTF-03**: Per-event-type notification toggles

### Theming

- **THEM-01**: Custom theme presets (Nord, Solarized, High Contrast)
- **THEM-02**: Custom branding (logo, colors)

### Distribution

- **DIST-01**: pip installable package
- **DIST-02**: Docker image
- **DIST-03**: Homebrew formula

## Out of Scope

| Feature | Reason |
|---------|--------|
| WebRTC P2P transfers | High complexity, browser compatibility issues, LAN HTTP is fast enough |
| Secure tunnel / remote access | v1 is LAN-only by design |
| Auto-sync between devices | Fundamentally different from file sharing; separate product concern |
| Admin dashboard | No auth in v1, no admin role needed |
| PWA / mobile app | Web works well on mobile; native app is v2+ |
| Desktop tray app | Electron/Tauri is a separate project |
| Plugin system | Over-engineering for v1 |
| File versioning | Filesystem doesn't support this natively; needs database |
| AI-powered search | Overkill for LAN file sharing |
| Scheduled transfers | Not a use case for ad-hoc LAN sharing |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| DISC-01 | Phase 1 | Pending |
| DISC-02 | Phase 1 | Pending |
| DISC-03 | Phase 1 | Pending |
| FILE-01 | Phase 2 | Pending |
| FILE-02 | Phase 2 | Pending |
| FILE-03 | Phase 2 | Pending |
| FILE-04 | Phase 2 | Pending |
| FILE-05 | Phase 2 | Pending |
| FILE-06 | Phase 2 | Pending |
| FILE-07 | Phase 2 | Pending |
| FILE-08 | Phase 2 | Pending |
| FILE-09 | Phase 2 | Pending |
| UIUX-02 | Phase 2 | Pending |
| UIUX-03 | Phase 2 | Pending |
| SRCH-01 | Phase 3 | Pending |
| SRCH-02 | Phase 3 | Pending |
| SRCH-03 | Phase 3 | Pending |
| MEDP-01 | Phase 3 | Pending |
| MEDP-02 | Phase 3 | Pending |
| MEDP-03 | Phase 3 | Pending |
| MEDP-04 | Phase 3 | Pending |
| MEDP-05 | Phase 3 | Pending |
| UIUX-01 | Phase 3 | Pending |
| RTME-01 | Phase 4 | Pending |
| RTME-02 | Phase 4 | Pending |
| RTME-03 | Phase 4 | Pending |
| RTME-04 | Phase 4 | Pending |
| RTME-05 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 32
- Unmapped: 0

---
*Requirements defined: 2026-03-09*
*Last updated: 2026-03-09 after roadmap creation*
