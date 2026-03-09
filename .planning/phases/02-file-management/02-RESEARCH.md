# Phase 2: File Management - Research

**Researched:** 2026-03-09
**Domain:** Full-stack file management (FastAPI backend + React frontend)
**Confidence:** HIGH

## Summary

Phase 2 transforms the read-only file browser from Phase 1 into a fully interactive file manager. The backend needs six new endpoints (upload, download, ZIP download, rename, delete, mkdir) all funneled through the existing `resolve_safe_path` for security. The frontend needs drag-and-drop upload with per-file progress bars (requiring XMLHttpRequest since fetch lacks upload progress events), folder navigation with URL-synced breadcrumbs, checkbox-based multi-select with batch operations, inline rename, and responsive mobile layout with file type icons.

The existing codebase already has `python-multipart` and `aiofiles` as dependencies, a clean router-per-domain pattern, Pydantic schemas for API responses, and a `FileEntry`/`DirectoryListing` model that extends naturally. The frontend uses React 19, Tailwind CSS v4 (with `@tailwindcss/vite` plugin), and a typed `apiFetch` client that needs extension for POST/DELETE/PUT methods. No React Router is installed; folder navigation URL sync should use native `URLSearchParams` + `history.pushState` + `popstate` events to stay lightweight.

**Primary recommendation:** Build backend endpoints first (upload, download, ZIP, rename, delete, mkdir), then layer frontend features in order of dependency: navigation/breadcrumbs, file operations, upload with progress, batch operations, responsive layout with icons.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full-page drop zone: overlay appears when dragging files over the browser window
- Explicit "Upload" button in toolbar for mobile users and discoverability
- Floating panel (like Google Drive) shows all active uploads with individual progress bars
- On failure: show error state with retry button per file (no auto-retry)
- File name conflicts: prompt user for each conflict (overwrite / rename / skip)
- Double-click folder row to navigate into it; single click selects the row
- Breadcrumbs as clickable path segments: Home / photos / vacation / 2024
- URL updates to reflect current path (e.g., /?path=photos/vacation) -- enables browser back button and link sharing
- Checkboxes always visible in a column on the left of each row
- "Select All" checkbox in table header with extended "Select all N items" link (Gmail-style)
- When items selected: header toolbar replaced with batch action bar showing "X selected", Download ZIP, Delete buttons
- Batch delete triggers a centered modal dialog: "Delete N files? This cannot be undone." with Cancel/Delete
- Delete confirmation via modal dialog (same pattern for single and batch delete)
- Rename: inline editing (click rename action, name becomes editable text field)

### Claude's Discretion
- File type icon set and mapping strategy (UIUX-03)
- Responsive breakpoints and mobile layout adjustments (UIUX-02)
- "New folder" UI trigger (button in toolbar vs context menu vs both)
- Download individual file behavior (direct browser download vs confirmation)
- Empty folder state messaging
- Exact styling of the upload overlay, floating panel, and modals

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FILE-01 | User can browse files in the shared folder | Existing `list_directory` + folder navigation with URL param sync |
| FILE-02 | User can navigate into subdirectories with breadcrumb trail | Breadcrumb component parsing path segments; `history.pushState` for URL sync |
| FILE-03 | User can upload multiple files via drag-and-drop with individual progress bars | FastAPI `UploadFile` + `aiofiles` chunked write; XHR `upload.onprogress` on client |
| FILE-04 | User can download individual files | FastAPI `FileResponse` serving files through `resolve_safe_path` |
| FILE-05 | User can select multiple files and download as ZIP | `zipstream-ng` for memory-efficient streaming ZIP via `StreamingResponse` |
| FILE-06 | User can delete files with confirmation dialog | `DELETE /api/files` endpoint + modal confirmation component |
| FILE-07 | User can rename files inline | `PATCH /api/files/rename` endpoint + inline editable text field |
| FILE-08 | User can create new folders | `POST /api/folders` endpoint + toolbar button |
| FILE-09 | User can batch delete selected files | Batch delete endpoint accepting list of paths + selection state management |
| UIUX-02 | Responsive layout works on mobile devices | Tailwind responsive breakpoints; stacked layout below `md` breakpoint |
| UIUX-03 | File type icons displayed for all files | `lucide-react` icons mapped by file extension |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | Backend API framework | Already in project, provides UploadFile, StreamingResponse |
| python-multipart | >=0.0.20 | Multipart form data parsing | Already a dependency; required for FastAPI file uploads |
| aiofiles | >=24.1.0 | Async file I/O | Already a dependency; non-blocking file write for uploads |
| Pydantic | >=2.10.0 | Schema validation | Already in project; all API responses use Pydantic models |
| React | ^19.2.0 | Frontend UI | Already in project |
| Tailwind CSS | ^4.2.1 | Styling | Already in project with @tailwindcss/vite plugin |

### New Dependencies Required
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| zipstream-ng | ^1.9.0 | Memory-efficient streaming ZIP | Generates ZIP data on-the-fly without buffering full archive in memory; avoids OOM for large batches |
| lucide-react | ^0.577.0 | File type icons | Tree-shakable SVG icons; consistent design; has dedicated file-type icons (FileText, FileImage, FileMusic, FileCode, FileArchive, FileVideo, etc.) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| zipstream-ng | stdlib `zipfile` + BytesIO | Works but loads entire archive into memory; fails on large file sets |
| lucide-react | Inline SVGs / emoji | Emojis already used in Phase 1 but look unprofessional and lack coverage; inline SVGs are maintenance burden |
| React Router | Native URL API | React Router is heavy for single query param; native `URLSearchParams` + `pushState` is sufficient |
| fetch API for uploads | XMLHttpRequest | fetch lacks upload progress events; XHR `upload.onprogress` is the only browser API for tracking upload progress |

**Installation:**
```bash
# Backend
uv add zipstream-ng

# Frontend
cd client && npm install lucide-react
```

## Architecture Patterns

### Backend: New API Endpoints

All endpoints MUST route through `resolve_safe_path` for path traversal protection. All MUST use strict types and raise exceptions rather than returning None (per CLAUDE.md rules).

```
POST   /api/files/upload?path={dir}       # Upload files to directory
GET    /api/files/download?path={file}     # Download single file
POST   /api/files/download-zip             # Download multiple files as ZIP (paths in body)
PATCH  /api/files/rename                   # Rename file/folder (old_path, new_name in body)
DELETE /api/files                          # Delete file(s) (paths in body)
POST   /api/folders                        # Create new folder (path in body)
GET    /api/files?path={dir}               # Already exists -- list directory
```

### Backend: File Service Extensions

```
server/app/services/file_service.py   -- add: upload_file, download_file, delete_paths, rename_path, create_folder, download_as_zip
server/app/models/schemas.py          -- add: UploadResult, RenameRequest, DeleteRequest, CreateFolderRequest, DownloadZipRequest
server/app/models/enums.py            -- add: ConflictResolution enum (OVERWRITE, RENAME, SKIP)
server/app/exceptions.py              -- add: FileConflictError, InvalidFileNameError
```

### Frontend: Component Structure

```
client/src/
  api/
    client.ts           # Extend: add apiPost, apiDelete, apiPatch, uploadWithProgress
    files.ts            # Extend: add upload, download, downloadZip, rename, delete, createFolder
  components/
    Breadcrumbs.tsx     # Clickable path segments
    FileList.tsx        # Extend: checkbox column, selection state, batch toolbar
    FileRow.tsx         # Extend: checkbox, double-click nav, right-click actions, inline rename, file icon
    FileIcon.tsx        # NEW: maps file extension to lucide icon
    UploadOverlay.tsx   # NEW: full-page drop zone overlay
    UploadPanel.tsx     # NEW: floating panel with per-file progress bars
    BatchToolbar.tsx    # NEW: "X selected" + Download ZIP + Delete buttons
    ConfirmDialog.tsx   # NEW: reusable modal for delete confirmation
    CreateFolderDialog.tsx  # NEW: modal/input for new folder name
    Toolbar.tsx         # NEW: contains Upload button, New Folder button
  hooks/
    usePathNavigation.ts   # NEW: URL param sync, breadcrumb parsing, navigation
    useFileSelection.ts    # NEW: checkbox state, select all, batch operations
    useUpload.ts           # NEW: XHR upload with progress tracking, conflict handling
    useDragDrop.ts         # NEW: dragenter/dragleave/drop event handling for full-page overlay
  types/
    files.ts            # Extend: add UploadState, SelectionState, ConflictAction enum
  App.tsx               # Refactor: folder navigation state, toolbar, upload integration
```

### Pattern 1: Async Chunked File Write (Upload)
**What:** Write uploaded file to disk asynchronously in chunks, never loading entire file into memory.
**When to use:** All file uploads.
```python
# Source: FastAPI community best practice + aiofiles docs
import aiofiles

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB chunks

async def save_upload(upload: UploadFile, destination: Path) -> int:
    """Save an UploadFile to disk in chunks. Returns bytes written."""
    bytes_written = 0
    async with aiofiles.open(destination, "wb") as out_file:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            await out_file.write(chunk)
            bytes_written += len(chunk)
    return bytes_written
```

### Pattern 2: XHR Upload with Progress
**What:** Use XMLHttpRequest for file upload to get real-time progress events. Fetch API does not support upload progress.
**When to use:** All file uploads from the browser.
```typescript
// Wrap XHR in a Promise for each file upload
function uploadFileWithProgress(
    file: File,
    targetPath: string,
    onProgress: (percent: number) => void,
): Promise<UploadResult> {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append("file", file);

        xhr.upload.addEventListener("progress", (event: ProgressEvent) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                onProgress(percent);
            }
        });

        xhr.addEventListener("load", () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve(JSON.parse(xhr.responseText));
            } else {
                reject(new ApiError(xhr.status, xhr.responseText));
            }
        });

        xhr.addEventListener("error", () => {
            reject(new Error("Upload failed: network error"));
        });

        xhr.open("POST", `/api/files/upload?path=${encodeURIComponent(targetPath)}`);
        xhr.send(formData);
    });
}
```

### Pattern 3: Streaming ZIP with zipstream-ng
**What:** Generate ZIP on-the-fly without buffering the full archive.
**When to use:** Batch download of multiple files as ZIP.
```python
# Source: zipstream-ng docs + FastAPI StreamingResponse
from zipstream import ZipStream
from fastapi.responses import StreamingResponse

def create_zip_response(file_paths: list[Path], base_dir: Path) -> StreamingResponse:
    zs = ZipStream()
    for file_path in file_paths:
        relative = file_path.relative_to(base_dir)
        zs.add_path(file_path, arcname=str(relative))
    return StreamingResponse(
        zs,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=download.zip"},
    )
```

### Pattern 4: URL-Synced Path Navigation (No React Router)
**What:** Sync folder path to URL query param using native browser APIs.
**When to use:** Folder navigation, breadcrumbs, back button support.
```typescript
// Custom hook: usePathNavigation
function usePathNavigation(): { currentPath: string; navigateTo: (path: string) => void } {
    const getPathFromUrl = (): string => {
        const params = new URLSearchParams(window.location.search);
        return params.get("path") ?? "";
    };

    const [currentPath, setCurrentPath] = useState<string>(getPathFromUrl());

    useEffect(() => {
        const handlePopState = (): void => {
            setCurrentPath(getPathFromUrl());
        };
        window.addEventListener("popstate", handlePopState);
        return () => window.removeEventListener("popstate", handlePopState);
    }, []);

    const navigateTo = (path: string): void => {
        const params = new URLSearchParams();
        if (path !== "") {
            params.set("path", path);
        }
        const newUrl = params.toString() !== "" ? `?${params.toString()}` : window.location.pathname;
        window.history.pushState({}, "", newUrl);
        setCurrentPath(path);
    };

    return { currentPath, navigateTo };
}
```

### Anti-Patterns to Avoid
- **Using `shutil.copyfileobj` for uploads:** Blocks the event loop. Use `aiofiles` chunked async write instead.
- **Using `fetch()` for upload progress:** Fetch API does not support upload progress events. Use XMLHttpRequest.
- **Loading entire ZIP into BytesIO:** Causes OOM for large file sets. Use `zipstream-ng` for streaming.
- **Using TypeScript `enum` keyword:** Project has `erasableSyntaxOnly: true`. Use `as const` objects.
- **Hardcoding file paths without `resolve_safe_path`:** Every user-supplied path MUST go through `resolve_safe_path` for traversal protection.
- **Returning None/null from functions:** Per CLAUDE.md, all functions must throw typed exceptions on error, never return null.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Streaming ZIP generation | Custom ZIP byte assembly | `zipstream-ng` | ZIP format has complex headers, CRC32, compression; library handles all correctly |
| File type icons | Custom SVG set or emoji mapping | `lucide-react` | 50+ file-related icons, tree-shakable, consistent design language, actively maintained |
| Upload progress tracking | Polling-based or websocket progress | XHR `upload.onprogress` | Native browser API, no dependencies, works in all browsers |
| Multipart form parsing | Manual request body parsing | FastAPI `UploadFile` + `python-multipart` | FastAPI handles spooled temp files, content-type detection, async interface |
| Path traversal protection | Custom string-based path checking | Existing `resolve_safe_path` | Already tested with 10+ edge cases including symlinks; proven safe |

**Key insight:** File operations have subtle security and correctness concerns (path traversal, race conditions, encoding). Reuse existing `resolve_safe_path` for ALL new endpoints and use proven libraries for ZIP and file parsing.

## Common Pitfalls

### Pitfall 1: Race Condition on File Conflict Check
**What goes wrong:** Check if file exists, then write -- another request writes between check and write.
**Why it happens:** Concurrent uploads to the same filename.
**How to avoid:** Use atomic operations where possible. For conflict resolution, the server should check-and-prompt at the start; the client sends the resolution choice (overwrite/rename/skip) with the actual write. If overwriting, write to a temp file first, then `os.replace()` (atomic on same filesystem).
**Warning signs:** Intermittent file corruption or partial writes in concurrent upload scenarios.

### Pitfall 2: Missing Path Traversal Check on New Endpoints
**What goes wrong:** New rename/delete/mkdir endpoints bypass `resolve_safe_path`.
**Why it happens:** Developer forgets to apply the guard to every new endpoint.
**How to avoid:** Every service function that accepts user paths MUST call `resolve_safe_path` as its first operation. Tests MUST include traversal attempt for every endpoint.
**Warning signs:** Any endpoint accepting a path parameter without `resolve_safe_path` call.

### Pitfall 3: Upload Progress Not Updating
**What goes wrong:** Progress bar stays at 0% or jumps to 100%.
**Why it happens:** Using `fetch()` instead of XHR, or not attaching to `xhr.upload.onprogress` (attaching to `xhr.onprogress` tracks download, not upload).
**How to avoid:** Attach progress listener to `xhr.upload` object, not `xhr` directly.
**Warning signs:** Progress events fire but show download progress (response bytes) instead of upload progress.

### Pitfall 4: ZIP Download Fails for Large File Sets
**What goes wrong:** Server runs out of memory or client receives incomplete ZIP.
**Why it happens:** Building entire ZIP in BytesIO before sending.
**How to avoid:** Use `zipstream-ng` which yields chunks; pair with `StreamingResponse`.
**Warning signs:** Memory usage spikes during ZIP downloads.

### Pitfall 5: Drag-and-Drop Events Fire Incorrectly
**What goes wrong:** Drop zone overlay flickers or fails to dismiss.
**Why it happens:** `dragenter`/`dragleave` events fire on child elements, causing false leave events.
**How to avoid:** Track a drag counter (increment on `dragenter`, decrement on `dragleave`). Show overlay when counter > 0, hide when counter reaches 0. Reset counter on `drop`.
**Warning signs:** Overlay flickers when dragging over text or child elements.

### Pitfall 6: File Name Encoding Issues
**What goes wrong:** Files with special characters (spaces, unicode, dots) break in URLs or on disk.
**Why it happens:** Missing `encodeURIComponent` on client, or missing safe-path validation on server.
**How to avoid:** Always `encodeURIComponent` path params on client. On server, validate new names (reject empty, reject `/`, reject `..`, reject null bytes). Use `Content-Disposition` with `filename*=UTF-8''` encoding for downloads.
**Warning signs:** Files with spaces show as `%20` in UI, or unicode filenames cause 500 errors.

### Pitfall 7: Select All Selects Only Visible Page
**What goes wrong:** "Select All" selects only the items rendered, not all items in the directory.
**Why it happens:** If pagination is implemented, selecting all means only the visible subset.
**How to avoid:** Phase 2 has no pagination (all items rendered). The "Select All" checkbox should simply set all entries as selected. The Gmail-style "Select all N items" banner covers the full-directory case.
**Warning signs:** User confusion when batch delete says "3 selected" but they expected all 50.

## Code Examples

### Backend: Upload Endpoint
```python
# Source: FastAPI docs + aiofiles pattern
from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import JSONResponse
from server.app.config import get_server_config
from server.app.services.file_service import resolve_safe_path

router = APIRouter(prefix="/api", tags=["files"])

@router.post("/files/upload")
async def upload_files(
    files: list[UploadFile],
    path: str = Query(""),
) -> dict:
    config = get_server_config()
    target_dir = resolve_safe_path(config.shared_folder, path)
    # ... validate target is directory, save each file with aiofiles
```

### Backend: Download Endpoint
```python
from fastapi.responses import FileResponse

@router.get("/files/download")
def download_file(path: str = Query(...)) -> FileResponse:
    config = get_server_config()
    file_path = resolve_safe_path(config.shared_folder, path)
    # Validate it's a file, not directory
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )
```

### Backend: Delete Endpoint
```python
from pydantic import BaseModel

class DeleteRequest(BaseModel):
    paths: list[str]

@router.delete("/files")
def delete_files(request: DeleteRequest) -> dict:
    config = get_server_config()
    deleted: list[str] = []
    for path_str in request.paths:
        resolved = resolve_safe_path(config.shared_folder, path_str)
        # Use shutil.rmtree for dirs, os.remove for files
```

### Frontend: File Icon Mapping
```typescript
// Source: lucide-react docs
import {
    File, Folder, FileText, FileImage, FileCode,
    FileMusic, FileArchive, FileVideo,
} from "lucide-react";

const EXTENSION_ICON_MAP: Record<string, typeof File> = {
    // Images
    jpg: FileImage, jpeg: FileImage, png: FileImage, gif: FileImage,
    svg: FileImage, webp: FileImage, bmp: FileImage,
    // Video
    mp4: FileVideo, mov: FileVideo, avi: FileVideo, mkv: FileVideo, webm: FileVideo,
    // Audio
    mp3: FileMusic, wav: FileMusic, flac: FileMusic, aac: FileMusic, ogg: FileMusic,
    // Code
    js: FileCode, ts: FileCode, py: FileCode, rs: FileCode, go: FileCode,
    jsx: FileCode, tsx: FileCode, html: FileCode, css: FileCode, json: FileCode,
    // Text/Docs
    txt: FileText, md: FileText, pdf: FileText, doc: FileText, docx: FileText,
    // Archives
    zip: FileArchive, tar: FileArchive, gz: FileArchive, rar: FileArchive, "7z": FileArchive,
};

function getFileIcon(fileName: string, isDirectory: boolean): typeof File {
    if (isDirectory) return Folder;
    const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
    return EXTENSION_ICON_MAP[ext] ?? File;
}
```

### Frontend: Drag Counter Pattern for Drop Zone
```typescript
// Prevents overlay flicker from child element events
const [dragCounter, setDragCounter] = useState(0);
const showOverlay = dragCounter > 0;

const handleDragEnter = (e: DragEvent): void => {
    e.preventDefault();
    setDragCounter((c) => c + 1);
};

const handleDragLeave = (e: DragEvent): void => {
    e.preventDefault();
    setDragCounter((c) => c - 1);
};

const handleDrop = (e: DragEvent): void => {
    e.preventDefault();
    setDragCounter(0);
    // Process e.dataTransfer.files
};
```

## Discretionary Recommendations

Per CONTEXT.md, these areas are Claude's discretion:

### File Type Icon Strategy (UIUX-03)
**Recommendation:** Use `lucide-react` with extension-based mapping. Map ~30 common extensions to 7 icon types (FileImage, FileVideo, FileMusic, FileCode, FileText, FileArchive, Folder). Default unknown extensions to generic `File` icon. All icons use `size={18}` and `currentColor` for consistency with text.

### Responsive Breakpoints (UIUX-02)
**Recommendation:** Use Tailwind's `md` breakpoint (768px) as the primary toggle. Below `md`: hide Size and Modified columns, show only checkbox + icon + name. Keep the same table structure but use `hidden md:table-cell` on optional columns. Upload panel stays bottom-right on all sizes. Batch toolbar stays full-width on all sizes.

### New Folder UI Trigger
**Recommendation:** Button in toolbar only (no context menu). Toolbar is always visible and discoverable. Clicking opens an inline input or small dialog for the folder name. Context menus are non-obvious on mobile.

### Download Individual File Behavior
**Recommendation:** Direct browser download (no confirmation). Clicking download should immediately trigger via an `<a>` tag with `download` attribute pointing to `/api/files/download?path=...`. No dialog -- downloads are non-destructive.

### Empty Folder State
**Recommendation:** Centered message "This folder is empty" with a subtle upload prompt: "Drag files here or use the Upload button". Keep it simple, no illustrations.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `fetch()` for upload progress | Still XHR (`upload.onprogress`) | Fetch upload progress API in development (2025+) | XHR remains the only working option for upload progress |
| `zipfile` + BytesIO in memory | `zipstream-ng` streaming | zipstream-ng 1.9.0 (Aug 2025) | Memory-efficient, supports Python 3.5-3.14 |
| Feather Icons | Lucide (community fork) | Lucide is the maintained fork | Lucide has more icons, active development, file-type specific icons |
| `shutil.copyfileobj` for uploads | `aiofiles` chunked async write | Best practice since FastAPI adopted async | Non-blocking event loop, better concurrency |

**Deprecated/outdated:**
- `react-dropzone`: Still works but adds unnecessary abstraction for what is a simple HTML5 drag-and-drop API
- `zipstream-new` / `python-zipstream`: Abandoned predecessors to `zipstream-ng`
- Synchronous XHR: Deprecated in browsers; async XHR remains fully supported

## Open Questions

1. **Maximum upload file size**
   - What we know: FastAPI/python-multipart uses `SpooledTemporaryFile` with a default spool size of 1MB before writing to disk. No explicit size limit by default.
   - What's unclear: Should the server enforce a max upload size? The use case is LAN file sharing where large files are expected.
   - Recommendation: No server-side limit for Phase 2 (LAN use case). If needed later, use `File(max_size=...)` in FastAPI.

2. **Concurrent upload limit**
   - What we know: Users might drag 50+ files at once.
   - What's unclear: How many should upload simultaneously vs. queued.
   - Recommendation: Upload 3 files concurrently, queue the rest. Show all in the upload panel with status (uploading/queued/done/failed).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest server/tests/ -x -q` |
| Full suite command | `uv run pytest server/tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FILE-01 | Browse files in shared folder | unit/integration | `uv run pytest server/tests/test_routes_files.py -x` | Existing (extend) |
| FILE-02 | Navigate subdirectories with breadcrumbs | unit/integration | `uv run pytest server/tests/test_routes_files.py -x` | Existing (extend) |
| FILE-03 | Upload multiple files with progress | integration | `uv run pytest server/tests/test_upload.py -x` | Wave 0 |
| FILE-04 | Download individual files | integration | `uv run pytest server/tests/test_download.py -x` | Wave 0 |
| FILE-05 | Download multiple as ZIP | integration | `uv run pytest server/tests/test_download.py::TestZipDownload -x` | Wave 0 |
| FILE-06 | Delete with confirmation | integration | `uv run pytest server/tests/test_file_operations.py::TestDelete -x` | Wave 0 |
| FILE-07 | Rename files inline | integration | `uv run pytest server/tests/test_file_operations.py::TestRename -x` | Wave 0 |
| FILE-08 | Create new folders | integration | `uv run pytest server/tests/test_file_operations.py::TestCreateFolder -x` | Wave 0 |
| FILE-09 | Batch delete selected files | integration | `uv run pytest server/tests/test_file_operations.py::TestBatchDelete -x` | Wave 0 |
| UIUX-02 | Responsive mobile layout | manual-only | N/A -- visual layout verification | N/A |
| UIUX-03 | File type icons | unit | `uv run pytest server/tests/test_file_service.py -x` | Extend for icon mapping if backend involved |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/ -x -q`
- **Per wave merge:** `uv run pytest server/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_upload.py` -- covers FILE-03 (upload endpoint, multi-file, path traversal on upload)
- [ ] `server/tests/test_download.py` -- covers FILE-04, FILE-05 (single download, ZIP download, path traversal on download)
- [ ] `server/tests/test_file_operations.py` -- covers FILE-06, FILE-07, FILE-08, FILE-09 (delete, rename, mkdir, batch delete, path traversal on each)

## Sources

### Primary (HIGH confidence)
- FastAPI official docs: [Request Files](https://fastapi.tiangolo.com/tutorial/request-files/) -- UploadFile API, multipart handling
- FastAPI official docs: [Custom Response](https://fastapi.tiangolo.com/advanced/custom-response/) -- StreamingResponse, FileResponse
- [MDN: XMLHttpRequest upload property](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/upload) -- upload progress events
- [Lucide React docs](https://lucide.dev/guide/packages/lucide-react) -- icon component API, tree-shaking, props
- [Tailwind CSS Responsive Design](https://tailwindcss.com/docs/responsive-design) -- mobile-first breakpoints

### Secondary (MEDIUM confidence)
- [zipstream-ng PyPI](https://pypi.org/project/zipstream-ng/) -- v1.9.0, streaming ZIP API
- [Jake Archibald: Fetch streams not for progress](https://jakearchibald.com/2025/fetch-streams-not-for-progress/) -- confirms fetch lacks upload progress
- [Webtips: Get Query Params in React without Router](https://webtips.dev/solutions/get-query-params-in-react) -- URLSearchParams + popstate pattern
- [FastAPI community discussion #9618](https://github.com/fastapi/fastapi/discussions/9618) -- aiofiles vs shutil for upload saves

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all core libraries already in project; new deps (zipstream-ng, lucide-react) are well-documented
- Architecture: HIGH -- follows existing router/service/schema pattern; all patterns verified against official docs
- Pitfalls: HIGH -- XHR vs fetch for progress is well-documented; drag counter pattern is established; path traversal guard already tested

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable stack, no fast-moving dependencies)
