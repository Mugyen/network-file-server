# Feature Landscape

**Domain:** LAN file sharing web application (browser-based, cross-platform)
**Researched:** 2026-03-09
**Confidence:** MEDIUM (based on training data knowledge of AirDrop, LocalSend, Snapdrop/PairDrop, ShareDrop, FileBrowser, and the project's own 35 feature ideas; web search unavailable for live verification)

## Competitive Landscape Context

The LAN file sharing space has clear tiers of products:

- **Zero-UI transfer tools** (AirDrop, LocalSend, Snapdrop/PairDrop): Focus on "select file, pick device, done." No file management. No browsing. No persistence.
- **Web-based file managers** (FileBrowser, Nextcloud, FileRun): Full file management with upload/download, but heavy, self-hosted, and enterprise-oriented. Not designed for casual LAN sharing.
- **This project's niche** sits between them: a lightweight, browser-based tool that combines the simplicity of AirDrop-style tools with the file management capability of a web file browser. The "scan QR, drop files, done" value proposition with actual file browsing and preview is the sweet spot.

---

## Table Stakes

Features users expect from any modern file sharing tool. Missing these and users leave immediately.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **File upload and download** | The entire point of the product. Every competitor has this. | Low | Already exists in current codebase. Needs multi-file support. |
| **Drag-and-drop upload** | Standard browser interaction since 2015. Click-to-upload-only feels broken. | Low | HTML5 Drag and Drop API. Non-negotiable for v1. |
| **Upload progress bars** | Users need feedback that something is happening, especially for large files. | Low | XHR/fetch progress events. Without this, users refresh and re-upload. |
| **Folder navigation** | Flat file list is useless with 20+ files. Competitors all support directory traversal. | Medium | Breadcrumbs + directory listing. Must sanitize paths to prevent traversal attacks. |
| **File deletion** | Users need to manage shared content. FileBrowser, Nextcloud all have this. | Low | Confirmation dialog required. Server-side validation of path. |
| **Search and filter** | Without search, folders with 50+ files are unusable. FileBrowser has this. LocalSend does not need it (no persistence). | Low | Client-side filtering by name is sufficient for v1. Type filter chips (images, docs, etc.) are expected. |
| **Sorting** | Name, size, date, type. Every file manager has this. | Low | Multiple sort keys with ascending/descending toggle. |
| **Responsive/mobile UI** | Most users will connect from phones. If it does not work on mobile, it does not work. | Medium | Must be touch-friendly. Current template is somewhat responsive but a React rewrite gives a clean start. |
| **Dark mode** | Expected in 2026. System detection via `prefers-color-scheme` plus manual toggle. | Low | CSS custom properties. Not having dark mode feels dated. |
| **QR code for connection** | Typing "192.168.1.47:6969" is the #1 friction point. AirDrop eliminates discovery entirely; QR is the web equivalent. | Low | Terminal ASCII QR + web UI QR. This is the viral hook. |
| **Multi-file upload** | Uploading one file at a time is not acceptable. Every competitor handles batches. | Low | File input with `multiple` attribute + drag-and-drop zone. |
| **File type icons** | Visual identification. Current codebase already has this with emoji icons. | Low | Already exists. Needs design polish in React rewrite. |

---

## Differentiators

Features that set this product apart from competitors. Not expected, but create "wow" moments and retention.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Cross-device clipboard sharing** | Turns the tool from "occasional file sharing" into "daily utility." No competitor in this tier offers it. AirDrop has Universal Clipboard but requires Apple ecosystem. | Medium | WebSocket real-time sync. The WebSocket infrastructure is reusable for notifications and file requests. Build this early because the infra pays dividends. |
| **In-browser media preview** | Transforms a file list into a media hub. Preview images, play videos, render PDFs, syntax-highlight code -- all without downloading. FileBrowser does basic preview; this project can go further with lightbox, slideshow, and streaming. | Medium-High | Incremental per file type. Images and text are trivial. Video streaming (range requests) and PDF (pdf.js) are moderate. Start with images + text + PDF. |
| **Batch operations (download as ZIP, batch delete)** | Power-user feature that saves time. FileBrowser has this; AirDrop/LocalSend/Snapdrop do not. "Download selected as ZIP" is the key action. | Medium | Streaming ZIP generation on the server. Checkbox multi-select UI. |
| **Real-time transfer notifications** | Makes the server feel alive. "File uploaded" toasts, device connected alerts. Without this, the admin has no awareness of activity. | Medium | WebSocket event streaming. Toast UI component. Shares infra with clipboard sync. |
| **File request system** | Unique feature. "Can someone share the agenda?" as a notification to all connected devices. No LAN file sharing tool does this. Clear value in meetings, classrooms, collaborative settings. | Medium-High | Request state management + WebSocket notifications + fulfillment flow. Builds on WebSocket infra from clipboard/notifications. |
| **Receive mode / digital drop box** | Upload-only mode for collecting files from others. "Upload your photos here" with a clean branded page. Teachers, photographers, event organizers -- each is a distinct use case. ShareDrop and Snapdrop have no concept of this. | Medium | Simplified upload-only view with optional password, expiry, and size limits. |
| **Device discovery and device list** | Shows who is connected. Makes the tool feel social. Foundation for "send to device" interactions. PairDrop does this well; FileBrowser does not. | Medium | WebSocket heartbeat + User-Agent parsing. |
| **Smart photo gallery mode** | Auto-detect image folders and show a masonry grid with thumbnails. Slideshow mode. For the "share event photos" use case, this is dramatically better than a file list. | Medium-High | Pillow for thumbnails, lazy loading, lightbox. Builds on media preview infrastructure. |
| **Resumable/chunked transfers** | Critical for large files on unreliable WiFi. A 2GB video failing at 95% is product-ending. LocalSend handles this well. This is the reliability feature. | High | Chunked upload protocol, server-side reassembly, HTTP Range for downloads. Most complex single feature. |
| **File rename** | In-place renaming. Small feature but expected in any file manager beyond the most basic. FileBrowser has it. | Low | Inline edit UI + server rename endpoint. |
| **Folder creation** | Ability to create new folders. Goes with folder navigation. | Low | Simple mkdir endpoint with path validation. |

---

## Anti-Features

Features to explicitly NOT build in v1. Either premature, out of scope, or actively harmful to the product's simplicity.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **User authentication / accounts** | Adds friction to the core "scan QR, drop files" flow. LAN tools should be open by default. This is a feature, not a missing feature. | Defer to v2. Consider optional PIN protection as a middle ground. |
| **E2E encryption** | Touches every file operation. Adds significant complexity (Web Crypto API, key management, encrypted storage). Correct crypto is hard; wrong crypto is worse than none. | Defer to v2. LAN is already a trusted network for most users. Document the security model honestly. |
| **WebRTC peer-to-peer transfers** | Complex plumbing (STUN/TURN, NAT traversal, fallback logic). The server-relay model is fine for LAN speeds. P2P only matters when the server is a bottleneck, which is a v2 problem. | Server-relay is adequate for v1. FastAPI with async can saturate gigabit LAN easily. |
| **Plugin system / extension API** | Massive scope increase. The product does not have enough users yet to justify an ecosystem. Build the core first. | Build features directly. Plugin system is a v3+ concern after product-market fit. |
| **Desktop tray app** | Different distribution model (Electron/Tauri). The browser-based approach is the differentiator -- it works on any device without installing anything. | Keep it browser-only. CLI is the server; browser is the client. |
| **PWA / mobile app** | Similar problem to desktop app. Adds distribution complexity. The web UI should be good enough on mobile that a native app is unnecessary. | Make the web UI mobile-excellent instead. |
| **Auto-sync / Dropbox-style sync** | File sync is an enormously complex problem (conflict resolution, delta sync, file watching). Entire companies (Dropbox, Syncthing) exist to solve this. | Manual transfer is the model. If users want sync, point them to Syncthing. |
| **File versioning** | Requires a versioned storage layer. Complex and storage-hungry. Not what users expect from a lightweight LAN sharing tool. | Single version. Overwrite with confirmation dialog is sufficient for v1. |
| **Admin dashboard** | Premature. The tool is for personal/small group use. An admin dashboard implies multi-tenancy and access control, which are v2 features. | Server logs to terminal. Basic transfer notifications in the web UI. |
| **AI-powered search** | Over-engineering for a LAN file sharing tool. Filename search is fine. Content-based search adds heavy dependencies (embedding models, indexing). | Client-side filename search with fuzzy matching is more than enough. |
| **Custom theming beyond dark mode** | Nice-to-have, not essential. Adding a theme editor, logo uploads, and color pickers is scope creep for v1. | Light mode + dark mode + system detection. That is the complete v1 story. |
| **Scheduled transfers** | Adds complexity (cron, background jobs) for a use case that barely exists in LAN sharing. Users transfer files when they want to transfer files. | Manual transfer only. |
| **Multi-server mesh** | Discovering and connecting multiple server instances is complex networking. The single-server model is the right scope for v1. | One server, many clients. |
| **Bandwidth throttling / QoS** | Over-engineering for v1. LAN bandwidth is typically abundant. Throttling matters in managed environments, which are v2+. | Let the OS handle bandwidth. |
| **Secure tunnel / remote access** | Exposing a LAN tool to the internet introduces serious security concerns. Requires auth, TLS, possibly a relay service. | LAN-only for v1. Users who need remote access can use Tailscale or similar. |

---

## Feature Dependencies

Understanding what must be built before what.

```
Core Server (FastAPI + static file serving)
  |
  +-- File CRUD (upload, download, delete, rename)
  |     |
  |     +-- Folder navigation (requires path-aware file listing)
  |     |     |
  |     |     +-- Folder creation
  |     |     +-- Breadcrumb navigation
  |     |
  |     +-- Multi-file upload (extends single upload)
  |     |     |
  |     |     +-- Drag-and-drop upload (extends multi-file)
  |     |     +-- Upload progress bars (requires XHR/fetch upload)
  |     |
  |     +-- Batch operations (requires multi-select UI)
  |           |
  |           +-- Batch download as ZIP (requires server-side ZIP streaming)
  |           +-- Batch delete (requires confirmation UI)
  |
  +-- Search / Filter / Sort (requires file listing API)
  |
  +-- QR Code (independent, requires IP detection -- already exists)
  |
  +-- Dark Mode (independent, CSS-only)
  |
  +-- WebSocket infrastructure
        |
        +-- Real-time notifications (first WebSocket consumer)
        |
        +-- Clipboard sharing (second WebSocket consumer)
        |
        +-- Device discovery (third WebSocket consumer)
        |
        +-- File request system (requires device discovery + notifications)

Media Preview (partially independent, partially requires file serving):
  Image preview --> Lightbox --> Gallery mode
  Text/code preview --> Syntax highlighting
  PDF preview --> pdf.js integration
  Video/audio preview --> Range request support (server-side)
```

---

## MVP Recommendation

The v1 MVP must feel like a **complete, polished product** -- not a half-baked file server. This means all table stakes plus 2-3 differentiators that define the product's identity.

**Prioritize (must ship in v1):**

1. **File upload/download with drag-and-drop and progress** -- The bare minimum. Without progress bars and drag-and-drop, the product feels amateur.
2. **Folder navigation with breadcrumbs** -- Flat file lists break at 20+ files. Navigation is non-negotiable.
3. **Search, filter, sort** -- Usability essential for any non-trivial shared folder.
4. **QR code instant connect** -- The viral hook. This is what makes people share the tool. Terminal ASCII QR + web UI QR.
5. **Dark mode with system detection** -- Table stakes in 2026. Low effort, high perception impact.
6. **File deletion, rename, folder creation** -- Basic file management operations. Without these it is a read-only viewer, not a file server.
7. **Multi-file upload** -- Single-file upload is unacceptable.
8. **Responsive mobile UI** -- Most connections will be from phones.
9. **In-browser media preview (images, text, PDF)** -- The differentiator that makes it feel like a product, not a directory listing. Start with images (lightbox), text (syntax highlight), and PDF (embed). Video streaming can follow.
10. **Real-time notifications (WebSocket toasts)** -- Makes the server feel alive. Also establishes the WebSocket infrastructure reused by clipboard and file requests.

**Second priority (ship shortly after MVP):**

11. **Clipboard sharing** -- The daily-use hook. Reuses WebSocket infra from notifications.
12. **Batch download as ZIP** -- Power-user feature, moderate effort.
13. **Batch delete** -- Completes the batch operations story.
14. **Device discovery** -- Shows connected devices. Foundation for social features.

**Defer (v1.x or v2):**

- **File request system** -- Depends on device discovery + notifications being solid first.
- **Receive mode / drop box** -- Great feature but adds a second "mode" to the product. Ship the primary mode first.
- **Smart gallery mode** -- Enhancement over basic image preview. Requires thumbnail generation (Pillow dependency).
- **Resumable transfers** -- Important for reliability but complex. The basic upload flow must work first.
- **Expiring share links** -- Requires token management and a separate "shared link" UI.
- **Video/audio streaming** -- Requires Range request support. Enhancement over basic media preview.

---

## Sources

- Project feature ideas (35 files in `/feature-ideas/` directory) -- HIGH confidence (first-party project vision)
- Training data knowledge of AirDrop, LocalSend, Snapdrop/PairDrop, ShareDrop, FileBrowser, Nextcloud -- MEDIUM confidence (not live-verified but these are well-established products with stable feature sets)
- Note: WebSearch and WebFetch were unavailable during this research session. Competitive feature analysis is based on training data knowledge of these products as of early 2025. Core feature sets of these products are stable enough that MEDIUM confidence is appropriate.
