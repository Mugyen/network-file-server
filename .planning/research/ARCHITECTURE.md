# Architecture Patterns

**Domain:** LAN file sharing web application (React + FastAPI)
**Researched:** 2026-03-09

## Recommended Architecture

A two-process development architecture (Vite dev server + FastAPI), collapsing to a single-process production architecture (FastAPI serves built React assets via StaticFiles mount). Communication flows through REST endpoints for CRUD operations and a single multiplexed WebSocket for all real-time features (clipboard sync, transfer notifications, file request updates).

```
+----------------------------------------------------+
|                  Client (Browser)                   |
|                                                     |
|  +-------------+  +-----------+  +---------------+  |
|  | File Browser |  | Clipboard |  | Media Preview |  |
|  | (React)      |  | (React)   |  | (React)       |  |
|  +------+------+  +-----+-----+  +-------+-------+  |
|         |               |                |           |
|  +------+---------------+----------------+-------+   |
|  |          React App Shell (Router, State)       |  |
|  |   - Zustand store (files, clipboard, notifs)   |  |
|  |   - WebSocket client (single connection)       |  |
|  |   - XHR upload with progress tracking          |  |
|  +-----+--------------------+--------------------+   |
+--------|--------------------|-----------------------+
         | REST (HTTP)        | WebSocket (WS)
         |                    |
+--------|--------------------|-----------------------+
|        v                    v         FastAPI        |
|  +-----------+     +----------------+                |
|  | REST API  |     | WS Manager     |                |
|  | Routers   |     | (ConnectionMgr)|                |
|  +-----+-----+     +-------+--------+                |
|        |                    |                         |
|  +-----+--------------------+--------+                |
|  |         Core Services              |               |
|  |  +------------+  +-------------+  |               |
|  |  | FileService|  | ClipService |  |               |
|  |  +------+-----+  +------+------+  |               |
|  |         |               |         |               |
|  |  +------+---------------+------+  |               |
|  |  |    Filesystem / State       |  |               |
|  |  +-----------------------------+  |               |
|  +-----------------------------------+               |
|                                                      |
|  +------------------+                                |
|  | StaticFiles mount| (serves React build in prod)   |
|  +------------------+                                |
+------------------------------------------------------+
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **React App Shell** | Routing, layout, theme (dark mode), global state container | All frontend components |
| **File Browser UI** | Directory listing, navigation, search/filter/sort, selection, drag-and-drop zone | REST API (`/api/files`), Upload Service |
| **Upload Service (frontend)** | XHR-based file upload with progress tracking, chunked upload for large files | REST API (`/api/upload`), WebSocket (progress broadcast) |
| **Clipboard UI** | Text input, clipboard history display, one-click copy | WebSocket (`clipboard` channel) |
| **Media Preview UI** | Lightbox for images, HTML5 player for video/audio, PDF viewer, code viewer | REST API (`/api/files/{path}/content`) for streaming |
| **Notification Toast System** | Renders toast notifications from WebSocket events | WebSocket (`notification` channel) |
| **QR Code Display** | Renders server URL as QR code on the landing page | REST API (`/api/server-info`) |
| **FastAPI REST Routers** | HTTP endpoints for files, upload, download, server info | Core Services |
| **WebSocket Manager** | Accepts connections, routes messages by type, broadcasts events | All connected clients, Core Services |
| **FileService** | Filesystem operations: list, read, write, delete, rename, mkdir, zip | Filesystem |
| **ClipboardService** | In-memory clipboard history, broadcast to subscribers | WebSocket Manager |
| **QR Code Generator** | Generates QR code as SVG/PNG from server URL | Called by REST router |

### Data Flow

**File Browse Flow:**
```
Browser                    FastAPI
  |                          |
  |-- GET /api/files?path= ->|
  |                          |-- FileService.list_directory(path)
  |                          |<- [{name, size, type, modified}, ...]
  |<- JSON file listing -----|
```

**File Upload Flow (with progress):**
```
Browser                           FastAPI                    All Clients
  |                                 |                           |
  |-- XHR POST /api/upload ------->|                           |
  |   (multipart/form-data)        |                           |
  |<- XHR progress events ---------|                           |
  |   (browser-native, per file)   |-- FileService.save()      |
  |                                |-- WS broadcast ---------->|
  |                                |   {type: "file_uploaded",  |
  |                                |    name, size, uploader}   |
  |<- 200 OK -------------------- |                           |
```

**File Download Flow (streaming):**
```
Browser                           FastAPI
  |                                 |
  |-- GET /api/files/{path}/dl --->|
  |                                |-- FileResponse(path)
  |<- Streamed file (chunked) -----|
  |   Content-Disposition: attach  |
```

**Media Preview Flow (range requests):**
```
Browser                           FastAPI
  |                                 |
  |-- GET /api/files/{path}/content|
  |   Range: bytes=0-1048575       |
  |                                |-- FileResponse with range support
  |<- 206 Partial Content --------|
```

**Clipboard Sync Flow:**
```
Client A                  FastAPI WS Manager           Client B
  |                            |                          |
  |-- WS: {type: "clipboard",  |                          |
  |        text: "hello"}  --->|                          |
  |                            |-- store in history       |
  |                            |-- broadcast ----------->|
  |                            |   {type: "clipboard",    |
  |                            |    text: "hello",        |
  |                            |    from: "Client A"}     |
```

**File Request Flow:**
```
Requester                 FastAPI WS Manager           All Clients
  |                            |                          |
  |-- WS: {type: "file_req",   |                          |
  |        desc: "Q4 report"}->|                          |
  |                            |-- store request          |
  |                            |-- broadcast ----------->|
  |                            |   {type: "file_req",     |
  |                            |    id, desc, status}     |
  |                            |                          |
  |                            |    (someone uploads)     |
  |                            |<- POST /api/upload ------|
  |                            |   ?request_id=X          |
  |<- WS: {type: "req_filled"} |                          |
```

## Patterns to Follow

### Pattern 1: Single Multiplexed WebSocket
**What:** One WebSocket connection per client, with message routing by `type` field.
**When:** Always. Do not open separate WebSocket connections per feature.
**Why:** Reduces connection overhead. LAN tool will have few clients (2-10 typically), but connection management should still be clean.

```typescript
// Frontend: single WebSocket with type-based dispatch
type WSMessage =
  | { type: "clipboard"; text: string; from: string }
  | { type: "notification"; event: string; detail: object }
  | { type: "file_request"; id: string; desc: string; status: string }
  | { type: "file_request_fulfilled"; requestId: string; filename: string };

function useWebSocket(url: string): void {
  const ws = useRef<WebSocket>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);
    ws.current.onmessage = (event: MessageEvent) => {
      const msg: WSMessage = JSON.parse(event.data);
      switch (msg.type) {
        case "clipboard":
          clipboardStore.addEntry(msg);
          break;
        case "notification":
          notificationStore.push(msg);
          break;
        case "file_request":
          requestStore.upsert(msg);
          break;
      }
    };
    return () => ws.current?.close();
  }, [url]);
}
```

```python
# Backend: ConnectionManager with typed message routing
from enum import Enum

class MessageType(str, Enum):
    CLIPBOARD = "clipboard"
    NOTIFICATION = "notification"
    FILE_REQUEST = "file_request"
    FILE_REQUEST_FULFILLED = "file_request_fulfilled"

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for connection in self.active_connections:
            await connection.send_json(message)

    async def broadcast_except(self, message: dict, exclude: WebSocket) -> None:
        for connection in self.active_connections:
            if connection is not exclude:
                await connection.send_json(message)
```

**Confidence:** HIGH -- FastAPI's own documentation recommends exactly this ConnectionManager pattern for WebSocket broadcasting.

### Pattern 2: XHR for Uploads (Not Fetch)
**What:** Use `XMLHttpRequest` for file uploads, not the Fetch API.
**When:** Any upload that needs progress tracking.
**Why:** The Fetch API has no native upload progress tracking. `XMLHttpRequest.upload.onprogress` provides real progress events with `loaded` and `total` bytes. This is well-established (supported since 2015) and reliable.

```typescript
function uploadFile(
  file: File,
  path: string,
  onProgress: (percent: number) => void
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);
    formData.append("path", path);

    xhr.upload.addEventListener("progress", (e: ProgressEvent) => {
      if (e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        reject(new UploadError(xhr.status, xhr.responseText));
      }
    });

    xhr.addEventListener("error", () => reject(new UploadError(0, "Network error")));
    xhr.open("POST", "/api/upload");
    xhr.send(formData);
  });
}
```

**Confidence:** HIGH -- MDN confirms Fetch API lacks upload progress; XHR.upload.onprogress is the standard approach.

### Pattern 3: FastAPI UploadFile for Server-Side
**What:** Use FastAPI's `UploadFile` (not `bytes`) for receiving file uploads.
**When:** Always for file uploads.
**Why:** `UploadFile` uses spooled temporary files -- stores small files in memory, automatically spills to disk for large files. `bytes` loads the entire file into memory, which will crash the server on large video files.

```python
from fastapi import APIRouter, UploadFile
from pathlib import Path

router = APIRouter(prefix="/api", tags=["files"])

@router.post("/upload")
async def upload_file(file: UploadFile, path: str) -> dict:
    target = resolve_safe_path(base_dir, path, file.filename)
    content = await file.read()
    target.write_bytes(content)
    await file.close()
    return {"filename": file.filename, "size": len(content)}
```

**Confidence:** HIGH -- FastAPI official documentation explicitly states UploadFile is recommended for large files.

### Pattern 4: Path Traversal Guard
**What:** Every filesystem operation must resolve the requested path and validate it stays within the shared directory.
**When:** Every file operation endpoint -- list, read, write, download, delete, rename.
**Why:** Without this, an attacker on the LAN can read/write arbitrary files on the host machine via `../../etc/passwd` style paths.

```python
from pathlib import Path

class PathTraversalError(Exception):
    pass

def resolve_safe_path(base_dir: Path, *segments: str) -> Path:
    """Resolve a path ensuring it stays within base_dir. Raises on traversal."""
    resolved = base_dir.joinpath(*segments).resolve()
    if not resolved.is_relative_to(base_dir.resolve()):
        raise PathTraversalError(
            f"Path {resolved} escapes base directory {base_dir}"
        )
    return resolved
```

**Confidence:** HIGH -- standard security pattern, existing codebase uses `secure_filename` from werkzeug but lacks full traversal guard for nested paths.

### Pattern 5: FileResponse for Downloads, StreamingResponse for Generated Content
**What:** Use `FileResponse` for serving existing files, `StreamingResponse` for dynamically generated content (zip archives).
**When:** Downloads use `FileResponse`. Batch download (zip) uses `StreamingResponse` with a generator.
**Why:** `FileResponse` automatically sets `Content-Length`, `ETag`, and `Last-Modified` headers, enabling browser caching and range requests for media streaming. `StreamingResponse` is needed for zip archives where the total size is unknown upfront.

```python
from fastapi.responses import FileResponse, StreamingResponse
import zipfile
import io

@router.get("/files/{file_path:path}/download")
async def download_file(file_path: str) -> FileResponse:
    safe_path = resolve_safe_path(base_dir, file_path)
    return FileResponse(
        path=safe_path,
        filename=safe_path.name,
        media_type="application/octet-stream",
    )

@router.post("/files/download-zip")
async def download_zip(file_paths: list[str]) -> StreamingResponse:
    def generate_zip():
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for fp in file_paths:
                safe = resolve_safe_path(base_dir, fp)
                zf.write(safe, safe.name)
        buffer.seek(0)
        yield buffer.read()

    return StreamingResponse(
        generate_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=files.zip"},
    )
```

**Confidence:** HIGH -- FastAPI documentation confirms FileResponse auto-sets headers for caching/range-requests.

### Pattern 6: Zustand for Frontend State (Not Redux, Not Context-only)
**What:** Use Zustand for global state management in React.
**When:** For file list state, clipboard history, notification queue, upload progress tracking, theme preference.
**Why:** Zustand is minimal (< 1KB), has no boilerplate (unlike Redux), supports subscriptions outside React (useful for the WebSocket handler), and avoids the re-render problems of React Context for high-frequency updates (upload progress, clipboard sync). React Context + useReducer is fine for simple state but causes unnecessary re-renders when used as a global store.

```typescript
import { create } from "zustand";

interface FileEntry {
  name: string;
  size: number;
  type: "file" | "directory";
  modified: string;
}

interface FileStore {
  files: FileEntry[];
  currentPath: string;
  setFiles: (files: FileEntry[]) => void;
  setCurrentPath: (path: string) => void;
}

const useFileStore = create<FileStore>((set) => ({
  files: [],
  currentPath: "/",
  setFiles: (files: FileEntry[]) => set({ files }),
  setCurrentPath: (path: string) => set({ currentPath: path }),
}));
```

**Confidence:** MEDIUM -- Zustand is the widely adopted lightweight state manager for React. React Context + useReducer is a viable alternative per React docs, but Zustand is a better fit here due to WebSocket integration outside component tree and high-frequency progress updates.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate WebSocket Connections Per Feature
**What:** Opening `/ws/clipboard`, `/ws/notifications`, `/ws/requests` as separate connections.
**Why bad:** Wastes resources, complicates connection lifecycle management, creates race conditions on connect/disconnect. The app has few real-time features -- a single multiplexed connection with message type routing is simpler and more reliable.
**Instead:** Single `/ws` endpoint, JSON messages with a `type` field, dispatch on the frontend.

### Anti-Pattern 2: Polling for File List Updates
**What:** `setInterval(() => fetchFiles(), 3000)` to keep the file list current.
**Why bad:** Wasteful, laggy (up to 3s delay), hammers the filesystem. The server already knows when files change because uploads and deletes go through API endpoints.
**Instead:** After any file mutation (upload, delete, rename, mkdir), broadcast a `{type: "notification", event: "files_changed"}` via WebSocket. The frontend re-fetches the file list only when notified.

### Anti-Pattern 3: Storing Files in Memory or Database
**What:** Reading files into Python memory or storing file metadata in SQLite.
**Why bad:** The filesystem IS the database for this application. Files already exist on disk. Duplicating metadata into a database creates sync issues. Reading large files into memory crashes the server.
**Instead:** Read the filesystem directly on each request. Use `os.scandir()` (not `os.listdir()`) for efficient directory listing with metadata. Cache nothing -- LAN latency is sub-millisecond, filesystem reads are fast.

### Anti-Pattern 4: Building a Custom Media Player
**What:** Writing custom video/audio player controls from scratch.
**Why bad:** Browser-native `<video>` and `<audio>` elements with `controls` attribute handle playback, seeking, volume, fullscreen. Custom players are hundreds of lines of code for worse UX.
**Instead:** Use native HTML5 media elements. FastAPI's `FileResponse` supports range requests via `ETag`/`Last-Modified` headers, enabling seek. The browser handles the rest.

### Anti-Pattern 5: Monolithic FastAPI Application File
**What:** Putting all endpoints in a single `main.py`.
**Why bad:** The existing Flask app is ~200 lines in one file. The rewrite will be 5-10x larger with WebSocket handling, file operations, clipboard, QR code, and file requests. A single file becomes unmaintainable past ~500 lines.
**Instead:** Use FastAPI's `APIRouter` pattern. One router per domain: `files.py`, `clipboard.py`, `server_info.py`, `websocket.py`. A `main.py` that imports and mounts them.

## Recommended Backend Project Structure

```
server/
  app/
    __init__.py
    main.py                  # FastAPI app, mounts routers + static files
    config.py                # Server configuration (shared folder, port, host)
    routers/
      __init__.py
      files.py               # File CRUD: list, upload, download, delete, rename
      clipboard.py           # Clipboard REST endpoints (history, clear)
      server_info.py         # Server info, QR code generation
      websocket.py           # WebSocket endpoint + ConnectionManager
    services/
      __init__.py
      file_service.py        # Filesystem operations, path resolution
      clipboard_service.py   # In-memory clipboard history
      qr_service.py          # QR code generation (SVG/PNG)
    models/
      __init__.py
      schemas.py             # Pydantic models for request/response
      enums.py               # MessageType, FileType, RequestStatus enums
    exceptions.py            # Custom exceptions (PathTraversalError, etc.)
```

## Recommended Frontend Project Structure

```
client/
  src/
    main.tsx                 # Entry point, mounts React app
    App.tsx                  # Router setup, layout, theme provider
    api/
      client.ts              # Base HTTP client (fetch wrapper)
      files.ts               # File API calls
      serverInfo.ts          # Server info API calls
    hooks/
      useWebSocket.ts        # WebSocket connection + message dispatch
      useFileUpload.ts       # XHR upload with progress tracking
    stores/
      fileStore.ts           # Zustand: file list, current path, selection
      clipboardStore.ts      # Zustand: clipboard entries
      notificationStore.ts   # Zustand: toast queue
      uploadStore.ts         # Zustand: upload progress per file
      themeStore.ts          # Zustand: dark/light mode preference
    components/
      layout/
        AppShell.tsx         # Header, sidebar, main content area
        Navbar.tsx           # Navigation between file browser, clipboard
      files/
        FileBrowser.tsx      # File list with selection, sort, filter
        FileRow.tsx          # Single file entry
        BreadcrumbNav.tsx    # Path breadcrumbs for folder navigation
        UploadZone.tsx       # Drag-and-drop zone + upload progress
        UploadProgress.tsx   # Individual file upload progress bar
      clipboard/
        ClipboardPanel.tsx   # Clipboard input + history
        ClipboardEntry.tsx   # Single clipboard item
      preview/
        PreviewModal.tsx     # Modal wrapper for all preview types
        ImagePreview.tsx     # Image lightbox with zoom
        VideoPreview.tsx     # HTML5 video player
        AudioPreview.tsx     # HTML5 audio player
        CodePreview.tsx      # Syntax-highlighted code viewer
        PdfPreview.tsx       # PDF viewer
      notifications/
        ToastContainer.tsx   # Toast notification stack
        Toast.tsx            # Individual toast
      qr/
        QrCodeDisplay.tsx    # QR code SVG render
      requests/
        FileRequestForm.tsx  # Create file request
        FileRequestList.tsx  # Active requests display
    types/
      files.ts               # FileEntry, UploadResult types
      websocket.ts           # WSMessage union type
      clipboard.ts           # ClipboardEntry type
      requests.ts            # FileRequest type
    utils/
      formatSize.ts          # Human-readable file sizes
      mimeTypes.ts           # MIME type to preview type mapping
```

## Suggested Build Order (Dependencies)

The architecture has clear dependency layers. Build from bottom up.

### Phase 1: Foundation (no real-time features)
**Build:** Backend project structure, FileService with path traversal guard, file listing REST endpoint, React app shell with router, basic file browser UI (list only), file download via FileResponse.
**Why first:** Everything else depends on the file browsing and serving infrastructure. This replaces the existing Flask app's core functionality.
**Dependencies:** None.

### Phase 2: Upload Infrastructure
**Build:** Upload endpoint (UploadFile), drag-and-drop zone, XHR upload with progress bars, multi-file upload.
**Why second:** Uploads are the second core operation. The XHR progress pattern is independent of WebSocket.
**Dependencies:** Phase 1 (file listing must work to verify uploads).

### Phase 3: WebSocket Infrastructure + Notifications
**Build:** ConnectionManager, single `/ws` endpoint, message type routing, notification toast system, broadcast on file upload/download events.
**Why third:** WebSocket is shared infrastructure for clipboard and file requests. Building it with notifications is the simplest way to verify it works end-to-end.
**Dependencies:** Phase 2 (notifications need file events to broadcast).

### Phase 4: Clipboard Sharing
**Build:** ClipboardService, clipboard UI panel, WebSocket clipboard channel, clipboard history.
**Why fourth:** First consumer of WebSocket bidirectional communication (notifications were broadcast-only).
**Dependencies:** Phase 3 (WebSocket infrastructure).

### Phase 5: File Operations (Batch, Folders, Search)
**Build:** Delete, rename, mkdir, folder navigation, batch select, batch download as zip, search/filter/sort.
**Why fifth:** These are independent of real-time features. Can be built in parallel with Phase 4 if desired.
**Dependencies:** Phase 1 (basic file operations), Phase 3 (broadcast file changes).

### Phase 6: Media Preview
**Build:** PreviewModal with type detection, image lightbox, video/audio player (HTML5 native), code syntax highlighting, PDF viewer.
**Why sixth:** Purely additive UI feature. Each file type preview is independent work that can be incremental.
**Dependencies:** Phase 1 (file content serving with range request support).

### Phase 7: QR Code + Server Info
**Build:** QR code generation (backend), QR display component, server info endpoint.
**Why seventh:** Small, self-contained feature. Nice polish but not a dependency for anything else.
**Dependencies:** Phase 1 (server must be running to have a URL to encode).

### Phase 8: File Request System + Dark Mode + Polish
**Build:** File request model, request form, request broadcasting, fulfillment flow, dark mode toggle with system detection, UI polish.
**Why last:** File requests are the most complex real-time feature (stateful + bidirectional + linked to uploads). Dark mode is pure theming.
**Dependencies:** Phase 3 (WebSocket), Phase 2 (upload linked to request fulfillment).

## Scalability Considerations

| Concern | At 2-5 devices (typical) | At 10-20 devices (classroom) | At 50+ devices (unlikely for v1) |
|---------|--------------------------|------------------------------|----------------------------------|
| WebSocket connections | In-memory list, no issues | In-memory list, no issues | Consider connection limits, may need async broadcast batching |
| File listing | `os.scandir()` per request, fast | Same, fast | Consider caching directory listings with short TTL |
| Upload throughput | Single-threaded uvicorn, fine | May bottleneck on large files | Run uvicorn with `--workers 2-4`, but WebSocket state must be shared (needs Redis or similar) |
| Clipboard history | In-memory list, fine | Same | Same, keep bounded (last 50 entries) |

**For v1 (LAN tool, 2-10 devices):** Single-process uvicorn is sufficient. No database, no Redis, no external dependencies. The in-memory ConnectionManager pattern from FastAPI docs is the right fit.

## Development vs Production Architecture

### Development
- **Frontend:** Vite dev server on `localhost:5173` with HMR
- **Backend:** FastAPI via `uvicorn` on `localhost:8000`
- **CORS:** FastAPI CORSMiddleware allowing `localhost:5173` origin
- **Proxy:** Vite config proxies `/api/*` and `/ws` to FastAPI (preferred over CORS for WebSocket)

### Production
- **Single process:** FastAPI serves built React assets via `StaticFiles(directory="client/dist", html=True)` mounted at `/`
- **API routes** mounted at `/api` take precedence over static file catch-all
- **No CORS needed:** Same origin
- **Start command:** `uv run uvicorn app.main:app --host 0.0.0.0 --port 8080`

```python
# app/main.py - production static file serving
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI()

# API routers first (take precedence)
app.include_router(files_router)
app.include_router(clipboard_router)
app.include_router(server_info_router)

# WebSocket endpoint
app.include_router(websocket_router)

# React SPA catch-all (must be last)
client_dist = Path(__file__).parent.parent / "client" / "dist"
if client_dist.exists():
    app.mount("/", StaticFiles(directory=str(client_dist), html=True), name="spa")
```

**Confidence:** HIGH -- FastAPI docs confirm `StaticFiles(html=True)` serves `index.html` for unmatched routes, enabling SPA client-side routing.

## Sources

- FastAPI WebSocket documentation: https://fastapi.tiangolo.com/advanced/websockets/ -- ConnectionManager pattern, broadcast, WebSocketDisconnect handling (HIGH confidence)
- FastAPI file upload documentation: https://fastapi.tiangolo.com/tutorial/request-files/ -- UploadFile vs bytes, spooled file behavior (HIGH confidence)
- FastAPI project structure: https://fastapi.tiangolo.com/tutorial/bigger-applications/ -- APIRouter pattern, modular project layout (HIGH confidence)
- FastAPI custom responses: https://fastapi.tiangolo.com/advanced/custom-response/ -- FileResponse, StreamingResponse for file serving (HIGH confidence)
- FastAPI static files: https://fastapi.tiangolo.com/tutorial/static-files/ -- StaticFiles mount, html=True for SPA (HIGH confidence)
- MDN XMLHttpRequest.upload: https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload -- upload progress events (HIGH confidence)
- MDN Fetch API: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch -- confirms Fetch lacks upload progress (HIGH confidence)
- React state management: https://react.dev/learn/managing-state -- useReducer, Context, state patterns (HIGH confidence)
- Zustand recommendation: MEDIUM confidence -- based on training data, not verified via official source in this session. Alternative (React Context + useReducer) is documented by React team.
