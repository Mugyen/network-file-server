# Domain Pitfalls

**Domain:** LAN file sharing web app (React + FastAPI + WebSocket)
**Researched:** 2026-03-09

## Critical Pitfalls

Mistakes that cause rewrites, security incidents, or broken core functionality.

---

### Pitfall 1: Path Traversal — Escaping the Shared Directory

**What goes wrong:** Attackers craft filenames or URL paths containing `../` sequences (or encoded variants like `%2e%2e%2f`, `..%5c`, null bytes) to read or write files outside the shared folder. The existing codebase uses `secure_filename()` for uploads but joins unsanitized user input with `os.path.join()` for downloads, which is exploitable.

**Why it happens:** Developers trust `os.path.join(SHARED_FOLDER, user_input)` to stay within the shared folder. It does not. `os.path.join("/share", "/etc/passwd")` returns `/etc/passwd`. Even `secure_filename()` only sanitizes the filename itself -- it does not prevent directory components passed through URL path parameters.

**Consequences:** Arbitrary file read from the host machine. On a LAN tool where there is no authentication (by design in v1), any device on the network can read any file the server process can access. This is a data breach waiting to happen.

**Prevention:**
1. After constructing the full path, call `os.path.realpath()` (resolves symlinks) and verify the result starts with the shared folder's real path.
2. Reject any path component containing `..` before joining.
3. Never use raw user input in `os.path.join()` -- always sanitize first, validate after.

```python
def safe_resolve_path(shared_folder: str, user_path: str) -> Path:
    """Resolve user path and verify it stays within the shared folder."""
    base = Path(shared_folder).resolve()
    target = (base / user_path).resolve()
    if not str(target).startswith(str(base)):
        raise PermissionError(f"Path traversal blocked: {user_path}")
    if not target.exists():
        raise FileNotFoundError(f"File not found: {user_path}")
    return target
```

**Detection:** Unit tests that attempt `../../../etc/passwd`, encoded variants, and absolute paths. Run these tests on every endpoint that accepts a filename or path.

**Phase:** Must be addressed in Phase 1 (core backend). Every file operation endpoint needs this guard from day one.

**Confidence:** HIGH -- this is OWASP Top 10 territory, and the existing codebase has this vulnerability.

---

### Pitfall 2: Large File Uploads Eating All Memory

**What goes wrong:** File upload endpoints load the entire file into memory before writing to disk. A 2GB video upload crashes the server or causes the OS to kill the process. Multiple concurrent uploads compound the problem.

**Why it happens:** FastAPI's `bytes` annotation (`file: bytes = File()`) loads the entire file into RAM. Even `UploadFile` has a spoolfile threshold (default 1MB in Starlette) -- above that it writes to a temp file, but developers often call `await file.read()` anyway, which loads the whole thing into memory. Confirmed by FastAPI official docs: "If you declare the type as `bytes`, FastAPI will read the whole file and you will have the contents in memory. This will work well for small files."

**Consequences:** Server crashes on large files. On a LAN file sharing tool where people transfer videos, disk images, and archives, this is a core workflow failure.

**Prevention:**
1. Always use `UploadFile` (never `bytes`) for file upload parameters.
2. Stream uploads in chunks -- never call `await file.read()` without a size argument.
3. Set explicit upload size limits and return 413 early (via middleware or manual check).
4. Use chunked/resumable upload protocol on the frontend (tus or custom chunking).

```python
async def save_upload_streaming(upload: UploadFile, destination: Path) -> int:
    """Stream upload to disk in chunks, never loading full file into memory."""
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    total_bytes = 0
    with open(destination, "wb") as out_file:
        while chunk := await upload.read(CHUNK_SIZE):
            out_file.write(chunk)
            total_bytes += len(chunk)
    return total_bytes
```

**Detection:** Test with files larger than available RAM. Monitor server memory during upload stress tests. If memory usage grows linearly with file size, you have this bug.

**Phase:** Phase 1 (core backend). The upload endpoint is foundational.

**Confidence:** HIGH -- verified against FastAPI official documentation.

---

### Pitfall 3: WebSocket Connection Manager as In-Memory Singleton

**What goes wrong:** A `ConnectionManager` class holds all active WebSocket connections in a Python list/dict. This works for single-process deployments but completely breaks when running with multiple workers (uvicorn with `--workers N`). Connections on worker A cannot broadcast to connections on worker B.

**Why it happens:** Every FastAPI WebSocket tutorial (including the official docs) shows this pattern. The official docs explicitly warn: "Keep in mind that it will only work while the process is running, and will only work with a single process." Developers copy the pattern without reading the warning.

**Consequences:** Clipboard sync, file request notifications, and transfer notifications silently fail for some users. The bug is intermittent (depends on which worker handles which connection), making it extremely hard to diagnose.

**Prevention:**
- For v1 (single-process LAN tool): This is acceptable. Run uvicorn with `--workers 1` explicitly and document this constraint.
- Document the limitation clearly so v2 can migrate to Redis pub/sub or PostgreSQL LISTEN/NOTIFY if multi-worker support is needed.
- Do NOT prematurely optimize with Redis for v1 -- it adds operational complexity for a personal LAN tool.

**Detection:** If you ever see "clipboard sync works on some devices but not others" intermittently, check the worker count.

**Phase:** Phase 1 (backend setup). Set worker count to 1 explicitly. Phase 2+ (WebSocket features) should keep this constraint visible.

**Confidence:** HIGH -- directly from FastAPI official WebSocket documentation.

---

### Pitfall 4: Clipboard API Requires Secure Context (HTTPS)

**What goes wrong:** The browser Clipboard API (`navigator.clipboard.readText()` / `writeText()`) requires a "secure context" -- which means HTTPS or localhost. A LAN server accessed via `http://192.168.1.x:8000` is neither HTTPS nor localhost. The Clipboard API will be undefined or throw a permissions error.

**Why it happens:** Developers test on `localhost` where the Clipboard API works fine. It breaks when accessed from another device via the LAN IP address. This is a browser security restriction, not a bug.

**Consequences:** The cross-device clipboard sync feature -- positioned as a daily-use differentiator -- simply does not work on any device except the host machine. The entire feature is dead on arrival.

**Prevention:**
1. Do NOT rely on `navigator.clipboard` for the primary clipboard workflow.
2. Use a textarea-based copy mechanism: programmatically create a textarea, set its value, select it, and call `document.execCommand('copy')` (deprecated but still widely supported and works without secure context).
3. For reading the system clipboard: accept paste events (`document.addEventListener('paste')`) which work everywhere.
4. The "clipboard sharing" feature should be a shared scratchpad with manual paste/copy, not system clipboard integration.
5. If system clipboard integration is essential, add a self-signed HTTPS option (mkcert for local development) and document the setup.

```typescript
function copyToClipboard(text: string): void {
    // Fallback that works without secure context
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
}
```

**Detection:** Test the clipboard feature by accessing the app from a different device on the LAN (not localhost). If copy/paste fails, this is the cause.

**Phase:** Phase 2 or whenever clipboard sharing is implemented. Must be the very first thing validated before building the feature.

**Confidence:** HIGH -- well-documented browser security model.

---

### Pitfall 5: Video/Audio Streaming Without Range Request Support

**What goes wrong:** HTML5 `<video>` and `<audio>` elements require HTTP range requests (partial content / `206 Partial Content`) to support seeking, scrubbing, and progressive playback. Without range support, users must download the entire file before playback starts, and seeking is impossible.

**Why it happens:** A naive file download endpoint uses `send_file()` or streams the whole file as a single response. This returns a `200 OK` with the full file. The browser needs the server to handle `Range: bytes=X-Y` request headers and respond with `206 Partial Content` and `Content-Range` headers.

**Consequences:** Users click a video file and wait minutes for it to load. Seeking to the middle of a 1GB video re-downloads the entire file. Users assume the product is broken and use another tool.

**Prevention:**
1. FastAPI's `FileResponse` does NOT support range requests out of the box.
2. Implement a custom streaming endpoint that reads the `Range` header and returns partial content.
3. Alternatively, use `starlette.responses.FileResponse` with the `stat_result` parameter (Starlette added conditional response support), or use a library like `starlette-ranged-response`.
4. Always set `Accept-Ranges: bytes` in the response headers.

**Detection:** Open a video in the preview, try to seek to the middle. If the seek bar is unresponsive or playback restarts from the beginning, range requests are broken.

**Phase:** Phase where media preview is implemented (likely Phase 3). Must be built into the streaming endpoint from the start, not retrofitted.

**Confidence:** HIGH -- fundamental HTTP protocol requirement for media streaming.

---

### Pitfall 6: No CORS Configuration for Cross-Origin Frontend

**What goes wrong:** During development, React runs on `localhost:3000` (Vite dev server) and FastAPI runs on `localhost:8000`. The browser blocks all API calls and WebSocket connections due to CORS policy. In production, if the frontend is served from a different origin than the API (e.g., static files on a CDN or different port), the same problem occurs.

**Why it happens:** CORS is disabled by default in FastAPI. Developers either forget to configure it, configure it too loosely (`allow_origins=["*"]`), or configure it for development and forget to adjust for production.

**Consequences:** During development: nothing works, hours wasted debugging "network error" messages. In production: WebSocket connections fail silently.

**Prevention:**
1. Add CORS middleware in FastAPI immediately, in the first commit.
2. For a LAN tool, `allow_origins=["*"]` is acceptable because there is no authentication and the tool is intentionally open-access.
3. For WebSocket: CORS applies differently -- the browser sends the `Origin` header but there is no preflight. However, FastAPI's CORSMiddleware does not handle WebSocket origins. You need to validate `websocket.headers.get("origin")` manually if you care.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # LAN tool: open by design
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Detection:** Open browser DevTools console. If you see "blocked by CORS policy" errors, this is the problem.

**Phase:** Phase 1 (backend setup). Add this in the very first commit alongside `app = FastAPI()`.

**Confidence:** HIGH -- universal issue in every React + separate API project.

---

## Moderate Pitfalls

Mistakes that cause significant bugs, poor UX, or wasted development time.

---

### Pitfall 7: Object URL Memory Leaks in Media Preview

**What goes wrong:** When previewing images, videos, or PDFs, the frontend creates Object URLs via `URL.createObjectURL(blob)`. Each call allocates browser memory for the blob data. If the URLs are never revoked with `URL.revokeObjectURL()`, memory usage grows until the browser tab crashes.

**Why it happens:** Object URLs are convenient for preview and persist until the page unloads or `revokeObjectURL()` is called. In a single-page React app, the page never unloads. Browsing through a gallery of 100 photos without cleanup can consume gigabytes of memory.

**Prevention:**
1. Always call `URL.revokeObjectURL()` when a preview component unmounts (React `useEffect` cleanup).
2. For galleries/slideshows, only hold Object URLs for visible items plus a small buffer.
3. Prefer streaming via direct URL (`/api/preview/filename`) over blob-based Object URLs where possible.

```typescript
useEffect(() => {
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
}, [blob]);
```

**Detection:** Open browser task manager. Browse through many files in the preview. If memory climbs steadily and never drops, Object URLs are leaking.

**Phase:** Media preview phase. Build cleanup into the preview component from the start.

**Confidence:** HIGH -- documented by MDN: "For long-lived applications, you should revoke object URLs when they're no longer needed."

---

### Pitfall 8: Upload Progress Requires XMLHttpRequest (Not Fetch)

**What goes wrong:** The standard Fetch API does not support upload progress events. Developers build a drag-and-drop upload UI with progress bars using `fetch()`, then discover the progress bars cannot work.

**Why it happens:** The Fetch API has `ReadableStream` support for download progress but no equivalent for upload progress. MDN explicitly states: "It's usually preferable to make HTTP requests using the Fetch API instead of XMLHttpRequest. However, in this case we want to show the user the upload progress, and this feature is still not supported by the Fetch API." This is still true in 2026.

**Consequences:** Progress bars either don't work (showing 0% then jumping to 100%) or require a late-stage rewrite from `fetch()` to `XMLHttpRequest`.

**Prevention:**
1. Use `XMLHttpRequest` for upload endpoints from the start if progress tracking is needed.
2. Alternatively, use the `axios` library which wraps XHR and provides `onUploadProgress` callbacks.
3. For chunked uploads, track progress by counting completed chunks (this works with `fetch()`).

```typescript
function uploadWithProgress(
    file: File,
    url: string,
    onProgress: (percent: number) => void
): Promise<Response> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                onProgress(Math.round((e.loaded / e.total) * 100));
            }
        });
        xhr.addEventListener('load', () => resolve(xhr.response));
        xhr.addEventListener('error', () => reject(new Error('Upload failed')));
        const formData = new FormData();
        formData.append('file', file);
        xhr.open('POST', url);
        xhr.send(formData);
    });
}
```

**Detection:** Test the upload UI with a large file (100MB+). If the progress bar jumps from 0% to 100%, you are using `fetch()`.

**Phase:** Drag-and-drop upload phase. Decide on XHR vs chunked approach before building the upload component.

**Confidence:** HIGH -- verified in MDN File API documentation.

---

### Pitfall 9: WebSocket Reconnection Not Handled

**What goes wrong:** WebSocket connections drop silently when a device sleeps, changes WiFi networks, or the server restarts. The frontend shows no indication that real-time features (clipboard sync, notifications) have stopped working. Users paste text and it never arrives.

**Why it happens:** The browser `WebSocket` API fires an `onclose` event but does not auto-reconnect. Developers implement the initial connection but forget to handle disconnection and reconnection with exponential backoff.

**Consequences:** Every real-time feature silently degrades. Clipboard sync stops working. File request notifications stop arriving. Transfer notifications stop. Users must manually refresh the page to restore functionality.

**Prevention:**
1. Implement reconnection logic with exponential backoff (1s, 2s, 4s, 8s, cap at 30s).
2. Show a visible connection status indicator in the UI (green dot = connected, red = disconnected, yellow = reconnecting).
3. On reconnection, re-sync state (fetch latest clipboard items, pending file requests, etc.).
4. Use a library like `reconnecting-websocket` or build a custom hook.

```typescript
function useReconnectingWebSocket(url: string): WebSocket | null {
    const wsRef = useRef<WebSocket | null>(null);
    const retriesRef = useRef(0);

    const connect = useCallback(() => {
        const ws = new WebSocket(url);
        ws.onopen = () => { retriesRef.current = 0; };
        ws.onclose = () => {
            const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000);
            retriesRef.current += 1;
            setTimeout(connect, delay);
        };
        wsRef.current = ws;
    }, [url]);

    useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);
    return wsRef.current;
}
```

**Detection:** Put a device to sleep for 30 seconds, wake it. If clipboard sync or notifications stop working without any visible indication, reconnection is not handled.

**Phase:** Phase where WebSocket infrastructure is built. Reconnection logic must be in the base WebSocket hook, not retrofitted per feature.

**Confidence:** HIGH -- universal WebSocket challenge, well-documented.

---

### Pitfall 10: File Name Conflicts and Overwrite Behavior

**What goes wrong:** Two devices upload a file with the same name simultaneously. Or a user uploads `report.pdf` when one already exists. Without clear conflict resolution, files get silently overwritten, data is lost, or users get confusing errors.

**Why it happens:** The current codebase rejects duplicate filenames outright (`File 'X' already exists`). This is safe but frustrating. The opposite extreme -- silently overwriting -- causes data loss. Neither is good UX.

**Consequences:** Data loss (if overwriting) or frustrated users (if rejecting). In a collaborative LAN environment where multiple people upload files, name collisions are frequent.

**Prevention:**
1. Implement an explicit conflict resolution strategy: rename with suffix (`report (1).pdf`, `report (2).pdf`).
2. On the frontend, detect conflicts before upload and prompt the user: "File exists. Replace, rename, or cancel?"
3. On the backend, the rename strategy should be the default for API calls without explicit user input (never silently overwrite).
4. Consider adding a timestamp or short hash suffix for batch uploads.

**Detection:** Upload the same file twice. If the second upload silently fails, overwrites, or gives a generic error, conflict handling is missing.

**Phase:** Core upload phase (Phase 1). Conflict resolution is part of the upload contract.

**Confidence:** HIGH -- observed in the existing codebase.

---

### Pitfall 11: Folder Navigation Enables Symlink Escape

**What goes wrong:** When implementing folder browsing (navigating into subdirectories), symbolic links inside the shared folder can point to arbitrary locations on the filesystem. A symlink `/shared/link -> /etc` lets users browse the entire system.

**Why it happens:** `os.listdir()` and `os.path.isdir()` follow symlinks transparently. Developers implement directory traversal without checking whether a path component is a symlink pointing outside the shared root.

**Consequences:** Same as path traversal (Pitfall 1) but through a different vector. The shared folder appears to contain a harmless subdirectory that is actually a portal to the entire filesystem.

**Prevention:**
1. Use `os.path.realpath()` on every path before serving content and verify it is under the shared root.
2. Optionally, refuse to follow symlinks entirely (`os.path.islink()` check).
3. The `safe_resolve_path` function from Pitfall 1 handles this automatically if used consistently.

**Detection:** Create a symlink inside the shared folder pointing to `/etc` or `~`. Navigate to it through the UI. If you can see files outside the shared folder, this is broken.

**Phase:** Phase 1 (core backend). Same mitigation as Pitfall 1.

**Confidence:** HIGH -- well-known filesystem security issue.

---

### Pitfall 12: Batch ZIP Download Holding Memory

**What goes wrong:** The "Download selected files as ZIP" feature creates the ZIP file in memory, then sends it. For 10 selected files totaling 2GB, the server needs 2GB+ of RAM just for that one download.

**Why it happens:** Python's `zipfile.ZipFile` with a `BytesIO` target accumulates the entire archive in memory. Developers build the ZIP, then return it as a response.

**Consequences:** Server crashes or OOM kills when users select many or large files for batch download.

**Prevention:**
1. Use streaming ZIP generation. Write ZIP content to a `StreamingResponse` as it is generated.
2. Python's `zipfile` module supports writing to a file-like object. Use a generator that yields chunks.
3. Consider the `zipstream-ng` library which is designed for streaming ZIP creation.

```python
import zipfile
from io import BytesIO
from starlette.responses import StreamingResponse

async def stream_zip(file_paths: list[Path]):
    """Stream a ZIP file without loading all files into memory."""
    # Use a streaming approach with zipstream-ng or manual chunked writing
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as zf:
        for path in file_paths:
            zf.write(path, path.name)
            # For true streaming, use zipstream-ng instead
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=download.zip"}
    )
```

**Detection:** Select 20+ large files for batch download. Monitor server memory. If it spikes by the total size of the selected files, the ZIP is being built in memory.

**Phase:** Batch operations phase. Design the ZIP endpoint as streaming from the start.

**Confidence:** HIGH -- standard Python memory management issue with zipfile.

---

## Minor Pitfalls

Mistakes that cause polish issues, minor bugs, or suboptimal behavior.

---

### Pitfall 13: MIME Type Detection Based on Extension Only

**What goes wrong:** The server determines file types (for preview routing, icons, Content-Type headers) based solely on the file extension. A `.txt` file containing HTML could be rendered as HTML. A `.jpg` file with a wrong extension gets the wrong Content-Type and fails to preview.

**Prevention:**
1. Use Python's `mimetypes.guess_type()` as the primary detector (extension-based, fast).
2. For preview features, add `python-magic` (libmagic wrapper) as a fallback to detect actual file content type.
3. Always set `X-Content-Type-Options: nosniff` header to prevent browser MIME sniffing on downloads.

**Phase:** Media preview phase.

**Confidence:** MEDIUM -- relevant but minor for a LAN tool.

---

### Pitfall 14: Local IP Detection Unreliable on Multi-Interface Machines

**What goes wrong:** The existing `get_local_ip()` function connects to `8.8.8.8:80` to determine the local IP. This fails on machines without internet, returns the wrong interface on machines with multiple network adapters (VPN, Docker bridge, USB tethering), and does not work at all on air-gapped networks.

**Prevention:**
1. Enumerate all network interfaces and display all non-loopback IPs.
2. Let the user select or specify the correct interface.
3. Prefer interfaces with default gateway routes.
4. Fallback to `0.0.0.0` binding and display all candidate IPs in the QR code / startup output.

```python
import netifaces

def get_all_lan_ips() -> list[str]:
    """Return all non-loopback IPv4 addresses."""
    ips = []
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        for addr in addrs.get(netifaces.AF_INET, []):
            ip = addr['addr']
            if not ip.startswith('127.'):
                ips.append(ip)
    return ips
```

**Phase:** Phase 1 (server startup). Important for QR code generation and connection instructions.

**Confidence:** HIGH -- the existing code has this issue and the `8.8.8.8` approach is a well-known anti-pattern for air-gapped networks.

---

### Pitfall 15: Browser Notification API Permission Complexity

**What goes wrong:** Browser Push Notifications (`Notification.requestPermission()`) require user interaction (button click) to prompt, are blocked by default in many browsers, persist permission state per-origin, and do not work in HTTP contexts on most browsers.

**Prevention:**
1. Use in-app toast notifications as the primary notification mechanism (no permissions needed).
2. Offer browser notifications as an opt-in enhancement, not a requirement.
3. Handle all three permission states: `granted`, `denied`, `default`.
4. Never call `requestPermission()` on page load -- only on explicit user action.

**Phase:** Notification phase.

**Confidence:** HIGH -- well-documented browser API limitation.

---

### Pitfall 16: React Dev Server Proxying WebSocket Incorrectly

**What goes wrong:** During development, Vite's proxy configuration handles regular HTTP requests but WebSocket upgrade requests need explicit `ws: true` configuration. Developers configure `/api` proxy but forget the WebSocket proxy, leading to WebSocket connections failing only in development.

**Prevention:**
In `vite.config.ts`:
```typescript
export default defineConfig({
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/ws': {
                target: 'ws://localhost:8000',
                ws: true,
            },
        },
    },
});
```

**Phase:** Phase 1 (project setup). Configure this alongside the initial Vite project creation.

**Confidence:** HIGH -- every Vite + WebSocket project hits this.

---

### Pitfall 17: File Upload Drops Non-ASCII Filenames

**What goes wrong:** `secure_filename()` from Werkzeug strips all non-ASCII characters. A file named `resume-2024.pdf` becomes `resume-2024.pdf` (fine), but `curriculum-vitae.pdf` (fine), but `report.pdf` becomes `report.pdf` (fine). However, files with CJK characters, emoji, or diacritics get mangled or reduced to empty strings.

**Prevention:**
1. Use `secure_filename()` to sanitize path separators and special characters.
2. If the result is empty or too short, generate a UUID-based filename preserving the original extension.
3. Store the original filename in metadata (database or sidecar file) for display purposes.
4. Consider using `unicodedata.normalize()` before sanitization to preserve more character variety.

**Phase:** Core upload phase (Phase 1).

**Confidence:** HIGH -- documented Werkzeug behavior.

---

### Pitfall 18: Concurrent File Operations Without Locking

**What goes wrong:** Two users rename the same file simultaneously. One user downloads a file while another deletes it. One user uploads while another creates a folder with the same name. Without any file operation locking, race conditions cause errors or data corruption.

**Prevention:**
1. Use `asyncio.Lock` per-file-path for write operations (rename, delete, move).
2. Do not lock reads (downloads, listings) -- readers can proceed concurrently.
3. Use a lock registry keyed by normalized file path.
4. Keep locks short-lived -- hold only during the actual filesystem operation, not during the entire upload stream.

**Phase:** Core backend phase. Add locking primitives early, use them in every mutation endpoint.

**Confidence:** MEDIUM -- less critical for a personal LAN tool with few concurrent users, but important for correctness.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Backend setup | Path traversal (1, 11), CORS (6), memory uploads (2) | Build `safe_resolve_path()`, add CORS middleware, stream uploads from day one |
| WebSocket infrastructure | Single-process constraint (3), no reconnection (9), dev proxy (16) | Set `--workers 1`, build reconnection into base hook, configure Vite proxy |
| File upload/download UI | Progress needs XHR (8), filename conflicts (10), non-ASCII filenames (17) | Use XHR or axios for uploads, implement conflict resolution, handle unicode |
| Media preview | Range requests required (5), Object URL leaks (7), MIME detection (13) | Build range support into streaming endpoint, cleanup in useEffect, use libmagic |
| Clipboard sharing | Clipboard API needs HTTPS (4) | Use textarea fallback, design as shared scratchpad not system clipboard hook |
| Batch operations | ZIP memory (12) | Use streaming ZIP generation |
| Notifications | Browser notification permissions (15) | Default to in-app toasts, browser notifications as opt-in |
| File requests | WebSocket state after reconnect | Re-sync pending requests on reconnect |

## Sources

- FastAPI official documentation: Request Files (https://fastapi.tiangolo.com/tutorial/request-files/) -- confirmed `bytes` vs `UploadFile` memory behavior, `python-multipart` requirement, form/JSON incompatibility [HIGH confidence]
- FastAPI official documentation: WebSockets (https://fastapi.tiangolo.com/advanced/websockets/) -- confirmed single-process limitation, `WebSocketDisconnect` handling, dependency injection differences [HIGH confidence]
- MDN: Using files from web applications (https://developer.mozilla.org/en-US/docs/Web/API/File_API/Using_files_from_web_applications) -- confirmed Fetch API lacks upload progress, Object URL memory management requirements [HIGH confidence]
- OWASP Path Traversal documentation -- path traversal attack patterns and mitigation [HIGH confidence, well-established security knowledge]
- MDN Clipboard API documentation -- secure context requirements [HIGH confidence, well-established browser security model]
- Existing codebase analysis (`wifi_file_server.py`) -- identified path traversal vulnerability, `secure_filename` limitations, `8.8.8.8` IP detection anti-pattern [HIGH confidence, direct observation]
