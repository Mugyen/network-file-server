# Phase 1: Foundation and Discovery - Research

**Researched:** 2026-03-09
**Domain:** FastAPI backend + React SPA frontend + QR code discovery for LAN file server
**Confidence:** HIGH

## Summary

Phase 1 replaces the existing Flask+Jinja single-file server with a FastAPI backend and React SPA frontend. The existing codebase (`network_file_server.py`, ~200 lines) provides a working reference for CLI argument parsing, local IP detection, and basic file listing, but will be fully replaced. The new architecture uses FastAPI to serve REST API endpoints for file listing and server information, plus serves the built React SPA via a catch-all route in production. During development, Vite proxies API requests to FastAPI.

The QR code discovery feature generates both ASCII output for the terminal and SVG for the web UI using the `qrcode` Python library. Local IP detection uses the stdlib `socket` approach (already in the codebase) which works on LAN-connected machines, with `ifaddr` as a fallback for multi-interface machines. Path traversal protection is the critical security requirement -- every file operation must validate resolved paths stay within the shared folder boundary.

All package versions have been live-verified against PyPI and npm registries as of 2026-03-09. The stack is stable and mature. No CONTEXT.md exists for this phase, so all architectural decisions follow the project's established constraints (React + FastAPI, uv for Python).

**Primary recommendation:** Build backend-first with path safety and file listing API, then scaffold the React SPA with Vite and connect it to the API via proxy. Add QR code generation last as it is self-contained.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOUND-01 | Server starts with FastAPI backend serving React SPA | FastAPI StaticFiles with html=True serves built React assets; catch-all route pattern for SPA client-side routing; Vite proxy for development |
| FOUND-02 | CLI accepts folder path argument and optional port | argparse pattern from existing codebase; FastAPI app configuration via Pydantic settings or module-level config |
| FOUND-03 | Path traversal protection on all file operations | `Path.resolve()` + `is_relative_to()` guard function; must cover `../`, encoded variants, absolute paths, and symlinks |
| FOUND-04 | CORS configured for development (Vite proxy) | FastAPI CORSMiddleware with `allow_origins=["*"]` for LAN tool; Vite proxy config as preferred development approach |
| DISC-01 | QR code displayed in terminal on server start (ASCII) | `qrcode` library `print_ascii()` method outputs ASCII-art QR to terminal |
| DISC-02 | QR code displayed on web UI (SVG) | `qrcode.image.svg.SvgPathImage` factory generates SVG; serve via `/api/server-info` endpoint |
| DISC-03 | Local IP address auto-detected and displayed | Socket UDP trick (existing pattern) for primary IP; `ifaddr` library as fallback for multi-interface detection |
</phase_requirements>

## Standard Stack

### Core Backend

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 | HTTP framework + future WebSocket | Async-native, built-in OpenAPI docs, Pydantic validation, native WebSocket support via Starlette. Project decision. |
| Uvicorn | 0.41.0 | ASGI server | Standard production server for FastAPI. Use `uvicorn[standard]` for uvloop + httptools. |
| Pydantic | 2.12.5 | Data validation + response schemas | FastAPI's native validation. Rust-backed v2. Use strict types per project conventions. |
| python-multipart | 0.0.22 | File upload parsing | Required by FastAPI for `UploadFile`. Without it, multipart uploads silently fail. |
| aiofiles | 25.1.0 | Async file I/O | Prevents blocking event loop during file reads in async handlers. |
| qrcode | 8.2 | QR code generation (ASCII + SVG) | Mature library with `print_ascii()` for terminal and `SvgPathImage` factory for web. |
| ifaddr | 0.2.0 | Network interface enumeration | Cross-platform IP detection. Fallback for multi-interface machines where socket trick picks wrong IP. |

### Core Frontend

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.4 | UI framework | Project decision. Stable release with improved hooks. |
| Vite | 7.3.1 | Build tool + dev server | Standard React build tool. CRA is deprecated. Fast HMR, built-in proxy support. |
| TypeScript | 5.9.3 | Type safety | Project conventions require strict types. Non-negotiable. |
| Tailwind CSS | 4.2.1 | Utility-first CSS | v4 uses Rust engine, zero-config with `@tailwindcss/vite` plugin. Built-in dark mode via `dark:` variant. |
| @tailwindcss/vite | 4.2.1 | Vite integration for Tailwind | v4 replaces PostCSS config with a Vite plugin. Single `@import "tailwindcss"` in CSS. |

### Development + Testing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Python test framework | Standard Python test runner. |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing FastAPI async endpoints. |
| httpx | 0.28.1 | HTTP test client | FastAPI recommended test client for async tests. |
| Ruff | 0.15.5 | Python linter + formatter | Replaces flake8, black, isort. Rust-based, fast. |
| Vitest | 4.0.18 | Frontend test framework | Vite-native. Shares Vite config. |
| @testing-library/react | 16.3.2 | React component tests | Tests user behavior, not implementation details. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Tailwind CSS v4 | Tailwind CSS v3 | v3 requires PostCSS config and `tailwind.config.js`. v4 is zero-config with Vite plugin. v4 is stable and recommended. |
| ifaddr | netifaces | netifaces requires C compilation, often fails on macOS. ifaddr is pure Python, cross-platform. |
| Catch-all route for SPA | StaticFiles(html=True) only | StaticFiles html=True serves directory indexes but does not fully support SPA client-side routing for arbitrary paths. A catch-all FileResponse route is more reliable. |
| qrcode (Python) | qrcode.react (JS) | Server-side generation is simpler -- the URL is known server-side. Terminal ASCII QR requires the Python library regardless. |

**Installation:**

```bash
# Backend (Python) -- run from project root
uv add fastapi "uvicorn[standard]" pydantic python-multipart aiofiles qrcode ifaddr
uv add --dev pytest pytest-asyncio httpx ruff

# Frontend (React) -- run from client/ directory
npm create vite@latest client -- --template react-ts
cd client
npm install
npm install -D tailwindcss @tailwindcss/vite
```

## Architecture Patterns

### Recommended Project Structure

```
network-file-server/
  server/
    app/
      __init__.py
      main.py              # FastAPI app creation, middleware, router mounting
      config.py             # ServerConfig: shared_folder, port, host
      routers/
        __init__.py
        files.py            # GET /api/files -- directory listing
        server_info.py      # GET /api/server-info -- IP, QR SVG, port
      services/
        __init__.py
        file_service.py     # list_directory(), resolve_safe_path()
        qr_service.py       # generate_ascii(), generate_svg()
        network_service.py  # detect_local_ip()
      models/
        __init__.py
        schemas.py          # Pydantic: FileEntry, ServerInfo, DirectoryListing
        enums.py            # FileType enum
      exceptions.py         # PathTraversalError, FileNotFoundError
    tests/
      __init__.py
      conftest.py           # Fixtures: test client, temp shared folder
      test_file_service.py  # Path traversal tests, directory listing
      test_routes_files.py  # API endpoint integration tests
      test_routes_info.py   # Server info endpoint tests
      test_qr_service.py    # QR generation tests
      test_network.py       # IP detection tests
  client/
    src/
      main.tsx              # React entry point
      App.tsx               # Root component, base layout
      api/
        client.ts           # Base fetch wrapper
        files.ts            # fetchFiles() API call
        serverInfo.ts       # fetchServerInfo() API call
      components/
        FileList.tsx         # File listing table
        FileRow.tsx          # Single file row
        QrCodeDisplay.tsx    # QR code SVG render
        ServerInfo.tsx       # IP address + QR display
      types/
        files.ts             # FileEntry interface
        serverInfo.ts        # ServerInfo interface
      index.css             # Tailwind CSS import
    vite.config.ts          # Proxy config for dev
    tsconfig.json
    package.json
  pyproject.toml            # uv project config
  uv.lock
```

### Pattern 1: Path Traversal Guard (CRITICAL)

**What:** Every filesystem operation resolves the requested path and validates it stays within the shared directory.
**When:** Every endpoint that accepts a file path or filename -- list, download, any future operations.

```python
# server/app/services/file_service.py
from pathlib import Path

class PathTraversalError(Exception):
    """Raised when a resolved path escapes the shared directory."""
    pass

def resolve_safe_path(base_dir: Path, user_path: str) -> Path:
    """Resolve user path, ensuring it stays within base_dir.

    Raises PathTraversalError if the resolved path escapes base_dir.
    Raises FileNotFoundError if the resolved path does not exist.
    """
    resolved_base = base_dir.resolve()
    resolved_target = (resolved_base / user_path).resolve()
    if not resolved_target.is_relative_to(resolved_base):
        raise PathTraversalError(
            f"Path traversal blocked: '{user_path}' resolves outside shared directory"
        )
    return resolved_target
```

**Confidence:** HIGH -- `Path.is_relative_to()` is available in Python 3.9+. This handles `../`, encoded variants, absolute paths, and symlinks because `.resolve()` canonicalizes the path.

### Pattern 2: FastAPI Application Factory with Router Mounting

**What:** FastAPI app created in `main.py`, routers mounted with prefixes, middleware added at creation time.
**When:** Always. Avoids monolithic single-file pattern.

```python
# server/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.routers import files, server_info

def create_app() -> FastAPI:
    app = FastAPI(title="Network File Server")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(files.router)
    app.include_router(server_info.router)

    # SPA catch-all: serve React build in production
    client_dist = Path(__file__).parent.parent.parent / "client" / "dist"
    if client_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(client_dist / "assets")), name="assets")

        @app.get("/{path:path}")
        async def spa_catch_all(path: str) -> FileResponse:
            file_path = client_dist / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(client_dist / "index.html")

    return app

app = create_app()
```

**Confidence:** HIGH -- FastAPI docs confirm `APIRouter` pattern and `StaticFiles` mounting. The catch-all route pattern is the established approach for SPA serving.

### Pattern 3: Vite Dev Server Proxy to FastAPI

**What:** During development, Vite proxies `/api/*` requests to the FastAPI server.
**When:** Development only. In production, FastAPI serves everything.

```typescript
// client/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

**Confidence:** HIGH -- Vite docs confirm proxy configuration pattern.

### Pattern 4: QR Code Generation (Terminal + SVG)

**What:** Generate ASCII QR for terminal display at server start, and SVG QR served via API endpoint for web UI.
**When:** Server startup (ASCII) and on API request (SVG).

```python
# server/app/services/qr_service.py
import io
import qrcode
import qrcode.image.svg

def generate_ascii_qr(url: str) -> str:
    """Generate ASCII art QR code for terminal display."""
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make()
    buffer = io.StringIO()
    qr.print_ascii(out=buffer)
    buffer.seek(0)
    return buffer.read()

def generate_svg_qr(url: str) -> str:
    """Generate SVG QR code for web display."""
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(url, image_factory=factory)
    buffer = io.BytesIO()
    img.save(buffer)
    buffer.seek(0)
    return buffer.read().decode("utf-8")
```

**Confidence:** HIGH -- verified against `qrcode` PyPI documentation. `print_ascii()` and `SvgPathImage` are documented APIs.

### Pattern 5: Local IP Detection

**What:** Detect the machine's LAN IP address for QR code URL and startup display.
**When:** Server startup.

```python
# server/app/services/network_service.py
import socket
import ifaddr

def detect_primary_lan_ip() -> str:
    """Detect the primary LAN IP using UDP socket trick.

    Raises RuntimeError if no suitable IP can be determined.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        raise RuntimeError("Cannot detect LAN IP: no network connectivity")

def detect_all_lan_ips() -> list[str]:
    """Enumerate all non-loopback IPv4 addresses via ifaddr.

    Returns list of IP address strings. Raises RuntimeError if none found.
    """
    ips: list[str] = []
    for adapter in ifaddr.get_adapters():
        for ip_info in adapter.ips:
            if isinstance(ip_info.ip, str) and not ip_info.ip.startswith("127."):
                ips.append(ip_info.ip)
    if not ips:
        raise RuntimeError("No non-loopback IPv4 addresses found")
    return ips
```

**Confidence:** HIGH -- socket UDP trick is the established pattern (used in existing codebase). `ifaddr` is the modern replacement for `netifaces` with zero compilation requirement.

### Anti-Patterns to Avoid

- **Monolithic `main.py`:** Do not put all routes in one file. Use FastAPI `APIRouter` per domain (files, server_info). The existing Flask app is one file; the rewrite must not repeat this.
- **`os.path.join()` with raw user input:** Never construct paths by joining user input directly. Always resolve and validate with the `resolve_safe_path` guard.
- **`bytes` for file parameters:** Never use `file: bytes = File()` in upload endpoints. Always use `UploadFile` which uses spooled temp files.
- **`allow_credentials=True` with `allow_origins=["*"]`:** These are mutually exclusive per CORS spec. Since this is a no-auth LAN tool, omit `allow_credentials`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| QR code generation | Custom QR matrix renderer | `qrcode` library (8.2) | QR encoding has complex error correction. Library handles all QR versions and error correction levels. |
| Path traversal protection | Custom string sanitization | `Path.resolve()` + `is_relative_to()` | String manipulation misses edge cases (encoded chars, symlinks, null bytes). `resolve()` handles all canonicalization. |
| Local IP detection | Parsing `ifconfig`/`ipconfig` output | `socket` + `ifaddr` | Shell command parsing is OS-specific and fragile. `ifaddr` works cross-platform. |
| SVG generation | Manual SVG XML construction | `qrcode.image.svg.SvgPathImage` | SVG path construction for QR is non-trivial. Library generates clean, optimized SVG paths. |
| CORS handling | Custom header middleware | `FastAPI CORSMiddleware` | CORS has preflight, credential, and wildcard rules. Middleware handles all edge cases per spec. |
| CSS framework | Custom design system | Tailwind CSS v4 | Utility classes with dark mode, responsive design, and consistent spacing out of the box. |

## Common Pitfalls

### Pitfall 1: Path Traversal via `../` or Absolute Paths

**What goes wrong:** User crafts URL path containing `../../../etc/passwd` or encoded variants (`%2e%2e%2f`). Server reads/serves arbitrary files.
**Why it happens:** `os.path.join("/share", "/etc/passwd")` returns `/etc/passwd`. Developers trust join to stay within base directory.
**How to avoid:** Use `resolve_safe_path()` on EVERY endpoint that takes a file path. No exceptions.
**Warning signs:** Any endpoint that calls `os.path.join(base, user_input)` without subsequent path validation.

### Pitfall 2: CORS Not Configured -- Development API Calls Fail

**What goes wrong:** React on `localhost:5173` cannot reach FastAPI on `localhost:8000`. Browser blocks all requests.
**Why it happens:** CORS is disabled by default in FastAPI.
**How to avoid:** Add CORSMiddleware in the very first commit. For this LAN tool, `allow_origins=["*"]` is correct. Additionally, configure Vite proxy so most requests go through the proxy and avoid CORS entirely during development.
**Warning signs:** "blocked by CORS policy" in browser console.

### Pitfall 3: SPA Client-Side Routing Broken in Production

**What goes wrong:** User navigates to a React route like `/settings`, refreshes the page, and gets a 404 from FastAPI because no API route matches `/settings`.
**Why it happens:** `StaticFiles(html=True)` only serves `index.html` for directory paths, not arbitrary path segments.
**How to avoid:** Use the catch-all `@app.get("/{path:path}")` route that serves `index.html` for any path that does not match a static file. Mount API routers with `/api` prefix so they take precedence.
**Warning signs:** Page works on initial load but 404s on browser refresh at any non-root URL.

### Pitfall 4: Symlinks Escape Shared Folder

**What goes wrong:** A symlink inside the shared folder points to `/etc` or `~`. Users browse through it via the file listing.
**Why it happens:** `os.listdir()` and `Path.iterdir()` follow symlinks transparently.
**How to avoid:** `resolve_safe_path()` with `.resolve()` follows symlinks and then validates the resolved target stays within the base directory. This handles it automatically.
**Warning signs:** File listing showing directories that should not exist within the shared folder.

### Pitfall 5: Local IP Detection Returns Wrong Interface

**What goes wrong:** Machine has VPN, Docker bridge, or multiple network adapters. Socket trick returns the VPN IP instead of the WiFi LAN IP. QR code encodes the wrong address.
**Why it happens:** The UDP socket trick (`connect("8.8.8.8", 80)`) picks the interface with the default route, which may not be the WiFi adapter.
**How to avoid:** Display all detected LAN IPs at startup using `ifaddr`. Let the primary IP be the socket trick result, but show alternatives. Allow `--host` CLI override.
**Warning signs:** QR code URL works on some devices but not others on the same WiFi.

### Pitfall 6: Tailwind CSS v4 Configuration Confusion

**What goes wrong:** Developer follows v3 documentation (PostCSS plugin, `tailwind.config.js`, `@tailwind base/components/utilities` directives). None of this works with v4.
**Why it happens:** Most online tutorials are for v3. v4 has a completely different setup.
**How to avoid:** Use `@tailwindcss/vite` plugin (not `postcss` + `autoprefixer`). Single `@import "tailwindcss"` in CSS file. No `tailwind.config.js` needed for basic usage.
**Warning signs:** Tailwind classes have no effect; build succeeds but no styles applied.

## Code Examples

### File Listing API Endpoint

```python
# server/app/routers/files.py
from fastapi import APIRouter
from app.services.file_service import list_directory
from app.models.schemas import DirectoryListing
from app.config import get_server_config

router = APIRouter(prefix="/api", tags=["files"])

@router.get("/files", response_model=DirectoryListing)
async def get_files(path: str = "") -> DirectoryListing:
    config = get_server_config()
    return list_directory(config.shared_folder, path)
```

### Pydantic Response Schema

```python
# server/app/models/schemas.py
from pydantic import BaseModel
from app.models.enums import FileType

class FileEntry(BaseModel):
    name: str
    size: int
    size_display: str
    type: FileType
    modified: str

class DirectoryListing(BaseModel):
    path: str
    entries: list[FileEntry]

class ServerInfo(BaseModel):
    ip: str
    port: int
    url: str
    qr_svg: str
    all_ips: list[str]
```

### FileType Enum

```python
# server/app/models/enums.py
from enum import Enum

class FileType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"
```

### React File List Component (Minimal)

```typescript
// client/src/components/FileList.tsx
import { FileEntry } from "../types/files";

interface FileListProps {
  files: FileEntry[];
}

function FileList({ files }: FileListProps) {
  return (
    <table className="w-full">
      <thead>
        <tr className="text-left border-b">
          <th className="py-2">Name</th>
          <th className="py-2">Size</th>
          <th className="py-2">Modified</th>
        </tr>
      </thead>
      <tbody>
        {files.map((file) => (
          <tr key={file.name} className="border-b hover:bg-gray-50">
            <td className="py-2">{file.name}</td>
            <td className="py-2">{file.size_display}</td>
            <td className="py-2">{file.modified}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export { FileList };
```

### API Client

```typescript
// client/src/api/client.ts
const API_BASE = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`API error ${status}: ${body}`);
  }
}

async function apiFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }
  return response.json() as Promise<T>;
}

export { apiFetch, ApiError };
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Create React App | Vite | CRA deprecated 2023 | Use `npm create vite@latest -- --template react-ts` |
| Tailwind v3 (PostCSS + config file) | Tailwind v4 (Vite plugin + `@import`) | Tailwind v4 GA 2025 | No `tailwind.config.js` needed. Use `@tailwindcss/vite` plugin. |
| Flask + Jinja templates | FastAPI + React SPA | Project decision | Full rewrite. Flask code is reference only. |
| `netifaces` for IP detection | `ifaddr` | netifaces unmaintained since 2021 | ifaddr is pure Python, cross-platform, actively maintained |
| `requirements.txt` + pip | `pyproject.toml` + uv | pip is legacy | uv manages lockfile, venv, and Python version |

**Deprecated/outdated:**
- `requirements.txt` in the project root is stale (Flask 2.3.3) and conflicts with `pyproject.toml`. Should be removed or ignored.
- `network_file_server.py` and `templates/index.html` are the old Flask app. Kept for reference but replaced by the new architecture.
- `start_server.sh` references pip and the old entry point. Will need replacement.

## Open Questions

1. **SPA catch-all vs StaticFiles(html=True)**
   - What we know: `StaticFiles(html=True)` serves `index.html` for directory paths. The catch-all `/{path:path}` route approach is used in production by multiple FastAPI+React projects.
   - What's unclear: Whether Starlette's `html=True` mode has improved SPA support in recent versions to make the catch-all unnecessary.
   - Recommendation: Use the catch-all route pattern. It is explicit and well-tested. Mount `/assets` as StaticFiles for Vite's hashed asset files, and catch everything else with the FileResponse fallback to `index.html`.

2. **React 19 ecosystem compatibility**
   - What we know: React 19.2.4 is the current stable release. Tailwind, Vite, and TypeScript are framework-agnostic and work fine.
   - What's unclear: Whether all testing libraries (`@testing-library/react` 16.x) are fully compatible with React 19's concurrent features.
   - Recommendation: Proceed with React 19. Testing Library 16.x is designed for React 19. If issues arise, they will surface during test setup in Wave 0.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (backend) | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Framework (frontend) | Vitest 4.0.18 + @testing-library/react 16.3.2 |
| Config file (backend) | none -- see Wave 0 |
| Config file (frontend) | none -- see Wave 0 |
| Quick run command (backend) | `uv run pytest tests/ -x` |
| Quick run command (frontend) | `cd client && npx vitest run --reporter=verbose` |
| Full suite command | `uv run pytest tests/ && cd client && npx vitest run` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | FastAPI serves React SPA at root URL | integration | `uv run pytest tests/test_routes_spa.py -x` | Wave 0 |
| FOUND-02 | CLI accepts folder path and port | unit | `uv run pytest tests/test_config.py -x` | Wave 0 |
| FOUND-03 | Path traversal blocked for `../`, encoded, absolute, symlink | unit | `uv run pytest tests/test_file_service.py -x` | Wave 0 |
| FOUND-04 | CORS headers present on API responses | integration | `uv run pytest tests/test_cors.py -x` | Wave 0 |
| DISC-01 | ASCII QR code generated for terminal | unit | `uv run pytest tests/test_qr_service.py::TestAsciiQr -x` | Wave 0 |
| DISC-02 | SVG QR code served via API | integration | `uv run pytest tests/test_routes_info.py::TestQrSvg -x` | Wave 0 |
| DISC-03 | Local IP auto-detected | unit | `uv run pytest tests/test_network.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x` (backend quick)
- **Per wave merge:** `uv run pytest tests/ && cd client && npx vitest run`
- **Phase gate:** Full suite green before verify

### Wave 0 Gaps

- [ ] `server/tests/conftest.py` -- shared fixtures: test client via httpx `ASGITransport`, temp shared folder with sample files
- [ ] `server/tests/test_file_service.py` -- covers FOUND-03 (path traversal)
- [ ] `server/tests/test_routes_files.py` -- covers file listing API
- [ ] `server/tests/test_routes_info.py` -- covers DISC-02 (QR SVG endpoint)
- [ ] `server/tests/test_routes_spa.py` -- covers FOUND-01 (SPA serving)
- [ ] `server/tests/test_config.py` -- covers FOUND-02 (CLI args)
- [ ] `server/tests/test_cors.py` -- covers FOUND-04
- [ ] `server/tests/test_qr_service.py` -- covers DISC-01 (ASCII QR)
- [ ] `server/tests/test_network.py` -- covers DISC-03 (IP detection)
- [ ] `client/src/__tests__/` directory -- frontend component tests
- [ ] pytest + pytest-asyncio + httpx as dev dependencies: `uv add --dev pytest pytest-asyncio httpx`
- [ ] Vitest + testing-library as dev dependencies: `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
- [ ] `pyproject.toml` pytest config section (testpaths, asyncio_mode)

## Sources

### Primary (HIGH confidence)

- FastAPI official docs: Static Files -- https://fastapi.tiangolo.com/tutorial/static-files/ -- StaticFiles mounting
- FastAPI official docs: CORS -- https://fastapi.tiangolo.com/tutorial/cors/ -- CORSMiddleware parameters and constraints
- FastAPI official docs: Request Files -- https://fastapi.tiangolo.com/tutorial/request-files/ -- UploadFile vs bytes, python-multipart requirement
- Starlette Static Files docs -- https://www.starlette.io/staticfiles/ -- `html=True` behavior
- Vite server options docs -- https://vite.dev/config/server-options -- proxy configuration for API and WebSocket
- Tailwind CSS v4 install docs -- https://tailwindcss.com/docs/installation/using-vite -- `@tailwindcss/vite` plugin setup
- qrcode PyPI page -- https://pypi.org/project/qrcode/ -- print_ascii, SvgPathImage factory
- PyPI version registry -- live-verified all Python package versions 2026-03-09
- npm registry -- live-verified all Node package versions 2026-03-09

### Secondary (MEDIUM confidence)

- GitHub gist: FastAPI React SPA pattern -- https://gist.github.com/ultrafunkamsterdam/b1655b3f04893447c3802453e05ecb5e -- catch-all route for SPA
- ifaddr PyPI page -- https://pypi.org/project/ifaddr/ -- cross-platform IP enumeration

### Tertiary (LOW confidence)

- None. All findings verified against official sources or live package registries.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions live-verified against PyPI and npm registries
- Architecture: HIGH -- patterns sourced from FastAPI official documentation and established community practices
- Pitfalls: HIGH -- path traversal from OWASP + existing codebase analysis; CORS from FastAPI docs; SPA routing from community experience

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain, mature libraries)
