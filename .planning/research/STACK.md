# Technology Stack

**Project:** WiFi File Server (React + FastAPI rewrite)
**Researched:** 2026-03-09
**Confidence note:** WebSearch and WebFetch were unavailable during research. Versions are based on training data (cutoff May 2025) and should be verified via `uv add` / `npm install` at project init. Pinned versions use `>=` minimum known-good versions.

## Recommended Stack

### Backend Core

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| FastAPI | >=0.115 | HTTP framework + WebSocket | Async-native, built-in OpenAPI docs, native WebSocket support via Starlette, type-safe with Pydantic. The project needs concurrent file transfers and real-time WebSocket features -- FastAPI's async foundation handles both without blocking. | HIGH |
| Uvicorn | >=0.32 | ASGI server | The standard production server for FastAPI. Supports HTTP/1.1, WebSocket, and graceful shutdown. Use `uvicorn[standard]` extra for uvloop + httptools performance. | HIGH |
| Pydantic | >=2.9 | Data validation + serialization | FastAPI's native validation layer. Pydantic v2 is Rust-backed and dramatically faster than v1. Use strict mode for all models per project conventions. | HIGH |
| python-multipart | >=0.0.18 | File upload parsing | Required by FastAPI for `UploadFile` parameters. Without it, multipart form uploads silently fail. | HIGH |
| aiofiles | >=24.1 | Async file I/O | FastAPI is async but stdlib `open()` is blocking. aiofiles prevents file reads/writes from blocking the event loop during concurrent transfers. | HIGH |

### Frontend Core

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| React | >=19.0 | UI framework | Project decision is React. React 19 brings improved Suspense, use() hook, and better server component patterns. For a SPA that needs real-time updates and drag-and-drop, React's component model is the right fit. | MEDIUM (verify React 19 stable status) |
| Vite | >=6.0 | Build tool + dev server | Fast HMR, ESBuild-based dev, Rollup-based production builds. The standard React build tool in 2025+. Create React App is deprecated; Vite is the replacement. | HIGH |
| TypeScript | >=5.6 | Type safety | Project conventions require strict types. TypeScript catches interface mismatches between frontend and backend at compile time. Non-negotiable for a project with WebSocket message contracts. | HIGH |

### Real-Time / WebSocket

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| FastAPI WebSocket (built-in) | (comes with FastAPI) | Server-side WebSocket | FastAPI/Starlette has native WebSocket support. No additional library needed. Handles clipboard sync, transfer notifications, file request events, and device presence. | HIGH |
| Native WebSocket API | (browser built-in) | Client-side WebSocket | The browser's native `WebSocket` API is sufficient for this use case. Avoid Socket.IO -- it adds unnecessary protocol overhead and the LAN-only constraint means no fallback transports (long-polling) are needed. | HIGH |

### QR Code Generation

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| qrcode (Python) | >=8.0 | Server-side QR generation | Mature, well-maintained library. Generates both SVG (for web UI) and ASCII (for terminal). Use `qrcode[pil]` extra for PNG output via Pillow. The server URL is known server-side, so generate there and serve to clients. | HIGH |
| Pillow | >=11.0 | Image processing for QR | Required by `qrcode` for PNG/image output. Also useful for image thumbnail generation in media preview feature. | MEDIUM |

### Frontend State + Data Fetching

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| TanStack Query | >=5.62 | Server state management | Handles file listing caching, refetch on window focus, optimistic updates for uploads/deletes, upload mutation tracking. The standard approach for async server state in React. | HIGH |
| Zustand | >=5.0 | Client state management | Lightweight (1KB), no boilerplate, works naturally with React. Perfect for WebSocket connection state, clipboard history, UI preferences (dark mode, sort order), notification queue. Avoid Redux -- massive overkill for this app. | MEDIUM (verify v5 stable) |

### UI Components + Styling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Tailwind CSS | >=4.0 | Utility-first CSS | Rapid UI development, built-in dark mode via `dark:` variant, consistent design tokens, tiny production bundles via purging. Tailwind v4 uses a new Rust engine. | MEDIUM (verify v4 stable) |
| Lucide React | >=0.460 | Icons | Clean, consistent icon set. Tree-shakable (only bundles used icons). MIT licensed. Successor to Feather icons with active maintenance. | HIGH |
| Sonner | >=1.7 | Toast notifications | Purpose-built toast library. Handles stacking, dismissal, progress, and action buttons. Used for transfer notifications and WebSocket events. Lightweight alternative to react-toastify. | MEDIUM |

### File Operations

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| python-magic | >=0.4.27 | MIME type detection | Detects file types by content (not just extension). Critical for media preview -- need to know if a file is truly an image vs a renamed executable. Falls back to `mimetypes` stdlib for extension-based detection. | HIGH |
| zipstream-ng | >=1.8 | Streaming ZIP creation | Batch download creates ZIPs on-the-fly without buffering the entire archive in memory. Streams directly to the HTTP response. The original `zipstream` is unmaintained; `zipstream-ng` is the active fork. | MEDIUM |

### Development + Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.3 | Python test framework | Standard Python test runner. Use with pytest-asyncio for testing async FastAPI endpoints. | HIGH |
| pytest-asyncio | >=0.24 | Async test support | Required for testing FastAPI's async route handlers and WebSocket connections. | HIGH |
| httpx | >=0.28 | HTTP test client | FastAPI's recommended test client. Supports async, WebSocket testing via `httpx.ASGITransport`. Replaces the older `TestClient` approach for async tests. | HIGH |
| Vitest | >=2.1 | Frontend test framework | Vite-native test runner. Faster than Jest, shares Vite's config and transforms. Tests TypeScript and JSX without extra setup. | HIGH |
| Testing Library | >=16.1 | React component tests | `@testing-library/react` for component testing. Tests user behavior, not implementation details. | HIGH |
| Ruff | >=0.8 | Python linter + formatter | Replaces flake8, black, isort, and pyflakes in a single Rust-based tool. 10-100x faster than the tools it replaces. The standard Python linter in 2025. | HIGH |
| ESLint | >=9.0 | JS/TS linter | Flat config format in v9. Use with `@typescript-eslint/parser`. | HIGH |

### Infrastructure

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| uv | >=0.5 | Python package manager | Already in use in the project. Fast, Rust-based, replaces pip + venv + pip-tools. Handles lockfile, virtual env, and Python version management. | HIGH |
| Node.js | >=22 LTS | Frontend runtime | LTS version for build tooling stability. Only needed for development builds -- the production output is static files served by FastAPI. | HIGH |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Build tool | Vite | Create React App | CRA is deprecated and unmaintained. Vite is faster and actively developed. |
| Build tool | Vite | Next.js | Next.js is for SSR/full-stack React. This project serves a SPA from FastAPI -- no need for Next's server rendering. |
| CSS | Tailwind CSS | CSS Modules | CSS Modules work but are slower to develop with. Tailwind's utility classes enable rapid iteration and built-in dark mode support. |
| CSS | Tailwind CSS | shadcn/ui | shadcn provides pre-built components on top of Tailwind + Radix. Consider adding it if UI complexity grows, but start with raw Tailwind to keep the dependency tree minimal. |
| State | Zustand | Redux Toolkit | Redux is massive overkill for this app's state needs. Zustand is 1KB, zero boilerplate, and handles the same patterns. |
| State | Zustand | Jotai | Jotai is atomic state (bottom-up). Zustand's single-store model is simpler for this app's few global concerns (WebSocket state, preferences, notifications). |
| Data fetching | TanStack Query | SWR | TanStack Query has better mutation support (upload progress, optimistic updates) and more active development. SWR is simpler but lacks the mutation features this project needs. |
| WebSocket | Native WebSocket | Socket.IO | Socket.IO adds a custom protocol layer, requires a separate server library, and its fallback transports (long-polling, etc.) are unnecessary on a LAN where WebSocket always works. Native WebSocket is simpler and more performant. |
| QR | qrcode (Python) | qrcode.react (JS) | Generate server-side because the URL is known there. Serving a QR image is simpler than adding a JS QR library. Terminal ASCII QR also requires the Python library regardless. |
| Toasts | Sonner | react-toastify | Sonner is smaller, has a cleaner API, and better default styling. react-toastify works but is heavier. |
| ASGI server | Uvicorn | Hypercorn | Uvicorn is the FastAPI ecosystem standard. Hypercorn supports HTTP/2 but that's unnecessary for LAN use. |
| File MIME | python-magic | mimetypes (stdlib) | mimetypes only checks extensions, not file content. python-magic reads file headers for accurate detection. Use mimetypes as fallback only. |
| ZIP streaming | zipstream-ng | zipfile (stdlib) | stdlib zipfile buffers the entire archive in memory. zipstream-ng streams chunks, critical for batch download of large files. |
| Python linter | Ruff | flake8 + black + isort | Ruff replaces all three in one tool, runs 10-100x faster, and has better defaults. No reason to use the legacy tools in a new project. |

## Stack Architecture Overview

```
Browser (React SPA)
  |
  |-- HTTP (REST API) --> FastAPI --> Filesystem
  |
  |-- WebSocket ---------> FastAPI WebSocket Manager
  |                           |
  |                           +--> Clipboard sync
  |                           +--> Transfer notifications
  |                           +--> File request events
  |                           +--> Device presence
  |
  +-- Static assets served by FastAPI (production)
  +-- Vite dev server with proxy (development)
```

**Key architectural choice:** FastAPI serves both the API and the built React SPA in production. During development, Vite's dev server proxies API calls to FastAPI. This avoids CORS issues and simplifies deployment (single process).

## Installation

```bash
# Backend (Python)
uv add fastapi "uvicorn[standard]" pydantic python-multipart aiofiles
uv add "qrcode[pil]" pillow python-magic zipstream-ng
uv add --dev pytest pytest-asyncio httpx ruff

# Frontend (Node)
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query zustand sonner lucide-react
npm install -D tailwindcss @tailwindcss/vite vitest @testing-library/react @testing-library/jest-dom jsdom
npm install -D @typescript-eslint/parser @typescript-eslint/eslint-plugin eslint
```

**Note:** Exact versions will be resolved by uv and npm at install time. The `>=` constraints above are minimum known-good versions. Lock files (`uv.lock`, `package-lock.json`) should be committed for reproducibility.

## Version Verification Checklist

The following versions could not be live-verified (WebSearch/WebFetch/Bash were unavailable). Verify these at project initialization:

| Package | Claimed Min Version | Verify Command | Risk |
|---------|-------------------|----------------|------|
| React | >=19.0 | `npm view react version` | React 19 was released late 2024; should be stable but verify |
| Vite | >=6.0 | `npm view vite version` | Vite 6 was in development as of mid-2025; may still be v5.x |
| Tailwind CSS | >=4.0 | `npm view tailwindcss version` | Tailwind v4 was announced; verify GA status -- may need v3.x |
| Zustand | >=5.0 | `npm view zustand version` | v5 was in development; may still be v4.x |
| Ruff | >=0.8 | `uv run ruff --version` | Ruff moves fast; likely higher than 0.8 |

**Action:** Run the verify commands before writing any code. Adjust `package.json` and `pyproject.toml` accordingly. If a library is still on the prior major version, the API differences are minimal -- the architecture remains the same.

## Sources

- FastAPI documentation (fastapi.tiangolo.com) -- WebSocket support, file upload patterns
- Vite documentation (vite.dev) -- React template, proxy configuration
- TanStack Query documentation (tanstack.com/query) -- mutation patterns for file uploads
- Zustand GitHub (github.com/pmndrs/zustand) -- store patterns
- qrcode PyPI (pypi.org/project/qrcode) -- SVG and ASCII generation
- Tailwind CSS documentation (tailwindcss.com) -- dark mode, v4 changes

**Confidence caveat:** All sources are from training data (cutoff May 2025). No live verification was possible during this research session.
