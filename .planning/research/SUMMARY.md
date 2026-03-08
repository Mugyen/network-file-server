# Research Summary: WiFi File Server

**Domain:** LAN file sharing web application (browser-based, cross-platform)
**Researched:** 2026-03-09
**Overall confidence:** MEDIUM-HIGH (strong architectural patterns, well-known domain; version numbers need live verification due to unavailable web tools)

## Executive Summary

The WiFi File Server rewrite from Flask+Jinja to React+FastAPI is a well-scoped greenfield project in a mature domain. The LAN file sharing space has clear tiers -- zero-UI transfer tools (AirDrop, LocalSend), heavy web file managers (FileBrowser, Nextcloud) -- and this project sits in the sweet spot between them: lightweight, browser-based, with the simplicity of AirDrop and the file management of a web file manager.

The technology stack is straightforward and well-established. FastAPI provides async HTTP + native WebSocket support in a single framework. React with Vite is the standard frontend build. The key architectural decision is a single multiplexed WebSocket connection that serves all real-time features (clipboard sync, transfer notifications, file requests, device presence), avoiding the complexity of Socket.IO while meeting all requirements. FastAPI serves the built React SPA in production, making deployment a single-process affair.

The most critical pitfalls are security-related: path traversal vulnerabilities (the existing codebase is vulnerable), memory exhaustion from large file uploads, and the browser Clipboard API requiring HTTPS (which breaks the headline clipboard sharing feature over LAN HTTP). The Clipboard API issue is the single biggest technical risk -- the cross-device clipboard feature must be designed as a shared scratchpad with manual copy/paste, not a system clipboard integration.

WebSearch, WebFetch, and Brave API were all unavailable during this research session. All version numbers are based on training data (cutoff May 2025) with minimum version constraints. The architecture and library choices are high-confidence; exact version pins should be verified at project initialization by running `uv add` and `npm install`.

## Key Findings

**Stack:** FastAPI + Uvicorn (backend), React 19 + Vite + TypeScript (frontend), native WebSocket (real-time), Pydantic v2 (validation), TanStack Query (server state), Zustand (client state), Tailwind CSS (styling), qrcode (QR generation).

**Architecture:** Single-process production deployment. FastAPI serves REST API + WebSocket + built React SPA. One multiplexed WebSocket per client with message type routing. No database -- filesystem is the data store, in-memory state for WebSocket connections and clipboard.

**Critical pitfall:** Browser Clipboard API requires HTTPS/secure context. A LAN server accessed via `http://192.168.x.x` is not a secure context. The clipboard sharing feature must use textarea-based fallback, not `navigator.clipboard`.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation (Backend + Frontend Shell)** - Most dependencies flow from here
   - Addresses: FastAPI project structure, React SPA, file listing, download, folder navigation, path traversal guard
   - Avoids: Path traversal (Pitfall 1), CORS misconfiguration (Pitfall 6), monolithic file structure (Anti-Pattern 5)

2. **Upload Infrastructure** - Second core operation, independent of WebSocket
   - Addresses: Multi-file upload, drag-and-drop, progress bars, file deletion, rename, folder creation
   - Avoids: Memory exhaustion (Pitfall 2), Fetch API lacking upload progress (Pitfall 8), filename conflicts (Pitfall 10)

3. **WebSocket + Notifications** - Shared real-time infrastructure
   - Addresses: ConnectionManager, message routing, transfer notifications, device presence tracking
   - Avoids: Single-process limitation (Pitfall 3), no reconnection handling (Pitfall 9), dev proxy issues (Pitfall 16)

4. **Search, Sort, Filter + Batch Ops + QR Code** - File management completeness
   - Addresses: Client-side search/filter/sort, batch download as ZIP, batch delete, QR code display
   - Avoids: ZIP memory issues (Pitfall 12)

5. **Media Preview** - Transforms file list into media hub
   - Addresses: Image lightbox, video/audio streaming, PDF viewer, code syntax highlighting
   - Avoids: Missing range request support (Pitfall 5), Object URL memory leaks (Pitfall 7)

6. **Clipboard Sharing** - Daily-use differentiator
   - Addresses: Real-time clipboard sync, clipboard history, copy/paste
   - Avoids: Clipboard API HTTPS requirement (Pitfall 4) by using textarea fallback

7. **File Request System + Polish** - Advanced real-time feature
   - Addresses: Request creation, fulfillment, status tracking, dark mode, mobile polish
   - Avoids: Builds on proven WebSocket infra from Phase 3

**Phase ordering rationale:**
- Phase 1-2 establish the core product (browse + transfer files). Everything else depends on this working.
- Phase 3 (WebSocket) must come before Phases 5-6 because clipboard and notifications depend on it, but it should not block Phases 1-2 which are HTTP-only.
- Phase 4 (search/batch/QR) is largely independent of WebSocket and can be parallelized with Phase 3 or built after.
- Phase 5 (media preview) is additive -- each file type preview is incremental. It depends only on Phase 1 (file serving).
- Phase 6 (clipboard) is the riskiest feature due to the HTTPS/Clipboard API issue. Placing it later gives time to validate the textarea fallback approach.
- Phase 7 (file requests) is the most complex real-time feature and builds on all prior infrastructure.

**Research flags for phases:**
- Phase 1: Standard patterns, unlikely to need further research. FastAPI project structure and path safety are well-documented.
- Phase 3: WebSocket reconnection and state management may need deeper investigation during implementation. The base ConnectionManager pattern is well-documented, but edge cases (disconnect during upload, reconnect state sync) need care.
- Phase 5: Range request support in FastAPI/Starlette needs verification. The recommended approach (custom streaming endpoint or `starlette-ranged-response`) should be validated with the actual installed version.
- Phase 6: Clipboard API HTTPS restriction needs hands-on validation. The textarea fallback approach should be prototyped early, not assumed to work.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack choices | HIGH | FastAPI + React + Vite is the standard 2025 stack for this type of project. Core libraries are mature and well-documented. |
| Version numbers | LOW | Could not verify via PyPI/npm (all web tools unavailable). Minimum versions are from training data (May 2025 cutoff). Must verify at project init. |
| Features | MEDIUM-HIGH | Feature landscape is well-understood from existing products (LocalSend, FileBrowser, etc.) and project's own 35 feature ideas. Could not do live competitive analysis. |
| Architecture | HIGH | FastAPI SPA serving, WebSocket ConnectionManager, FileResponse patterns are all from official documentation. |
| Pitfalls | HIGH | Most pitfalls are from direct codebase analysis (existing vulnerabilities), official documentation warnings, and well-established security knowledge (OWASP). |

## Gaps to Address

- **Version verification:** All package versions need live verification. Run install commands before writing any code.
- **React 19 stable status:** React 19 was released in late 2024 but verify stability and ecosystem compatibility (TanStack Query, Zustand with React 19).
- **Tailwind CSS v4 readiness:** v4 uses a new Rust engine. Verify GA status -- may need v3.x if v4 is still in beta.
- **Vite 6 readiness:** May still be v5.x. API is similar either way.
- **Zustand v5 readiness:** May still be v4.x. API is similar either way.
- **Range request support in Starlette/FastAPI:** Verify the exact mechanism for video streaming. May need a custom middleware or `starlette-ranged-response` package.
- **python-magic cross-platform:** python-magic wraps libmagic, which requires system-level installation on macOS (Homebrew) and Windows. May want a pure-Python fallback.
- **Clipboard textarea fallback:** Needs hands-on prototyping on actual mobile devices to confirm `document.execCommand('copy')` still works in 2026 mobile browsers.
