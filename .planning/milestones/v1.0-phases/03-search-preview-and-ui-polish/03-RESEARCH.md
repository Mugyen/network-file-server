# Phase 3: Search, Preview, and UI Polish - Research

**Researched:** 2026-03-09
**Domain:** Client-side search/filter/sort, media preview modal, syntax highlighting, markdown rendering, dark mode, FastAPI range requests
**Confidence:** HIGH

## Summary

Phase 3 adds search/filter/sort to the file listing, a unified preview modal for all previewable file types, and dark mode. The existing codebase uses React 19 + Tailwind CSS v4 + Lucide icons on the frontend, and FastAPI + Starlette on the backend. The critical finding is that **Starlette 0.52.1 (already installed) natively supports HTTP Range requests on FileResponse** -- no custom streaming code is needed for video/audio seeking. The frontend needs three new libraries: `react-syntax-highlighter` for code preview, `react-markdown` for markdown rendering, and `remark-gfm` for GitHub-flavored markdown tables/strikethrough. Dark mode in Tailwind CSS v4 uses the `@custom-variant` CSS directive (not a JS config file), toggling a `.dark` class on `<html>`.

The search feature splits into client-side filtering (current folder, instant) and a backend search endpoint (recursive subfolder search). Sort is fully client-side since all data (name, size, modified) is already in the FileEntry response. The preview modal follows the existing ConfirmDialog overlay pattern (fixed inset-0, z-60, bg-black/50 backdrop).

**Primary recommendation:** Use `react-syntax-highlighter` with PrismLight build (register only needed languages) for code preview, `react-markdown` + `remark-gfm` for markdown, and a new `/api/files/preview` endpoint with `Content-Disposition: inline` for serving files to the browser. Range requests work out of the box with Starlette's FileResponse.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full-width search bar on its own dedicated row above the toolbar (not inside the toolbar)
- Recursive search into subfolders (requires a backend search endpoint that walks the directory tree)
- Search results display file paths relative to current folder
- Client-side filtering for current folder; backend endpoint for recursive subfolder search
- Horizontal row of toggleable pill/chip buttons below the search bar (multi-select)
- 10 categories: All, Images, Video, Audio, Documents, Text, Code, Markdown, Archives, Executables/Binaries
- Text is separate from Documents; Markdown is its own category
- No "Other" chip -- uncategorized files only appear under "All"
- Clickable column headers (Name, Size, Modified) with arrow indicator, toggle asc/desc
- Default sort: Name ascending
- Clicking a file opens a preview modal (pop-up overlay)
- Modal includes "Open in new tab" button
- Unified modal pattern for all previewable file types
- Image lightbox: gallery with next/prev arrows, keyboard support, position indicator, download button
- Video/audio: inline player with seeking in modal
- PDF: embedded in iframe using browser native PDF renderer
- Code files: syntax highlighting with line numbers
- Markdown files: rendered as HTML
- Non-previewable files: file info + download button
- File type category definitions (exact extensions listed in CONTEXT.md)

### Claude's Discretion
- Dark mode: toggle placement, system preference auto-detect, persistence (localStorage), transition animation
- Click interaction model: whether clicking file name opens preview, or separate preview icon
- Video/audio player styling and controls
- Image zoom behavior within lightbox
- Keyboard shortcuts for preview navigation (Escape to close, etc.)
- Mobile layout for filter chips (scrollable row, wrapping, etc.)
- Search debounce timing and empty state messaging
- Loading states for preview content
- Responsive breakpoints for search bar and chips

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRCH-01 | User can search files by name (instant client-side filtering) | Client-side filter on `files` array using `name.toLowerCase().includes(query)`. Debounced input (300ms). Backend endpoint for recursive subfolder search. |
| SRCH-02 | User can filter by file type category | Extension-to-category map shared between FileIcon and FilterChips. Multi-select chip toggles. Client-side filter chain. |
| SRCH-03 | User can sort by name, size, date modified, type | Pure client-side `Array.sort()` on FileEntry fields. Sort state: `{field, direction}`. Column headers get click handlers. |
| MEDP-01 | User can preview images in a lightbox with zoom | Native `<img>` tag in modal. Gallery navigation via filtered image list. CSS `transform: scale()` for zoom. `/api/files/preview` endpoint with `Content-Disposition: inline`. |
| MEDP-02 | User can stream video/audio in-browser with seeking | Native `<video>` and `<audio>` HTML5 elements. Starlette 0.52.1 FileResponse handles Range requests natively (206 Partial Content). Same preview endpoint. |
| MEDP-03 | User can view PDFs in embedded viewer | `<iframe src="/api/files/preview?path=...">` uses browser's built-in PDF renderer. No extra library needed. |
| MEDP-04 | User can view code files with syntax highlighting | `react-syntax-highlighter` with PrismLight build. Fetch file content as text, render with line numbers. |
| MEDP-05 | User can view markdown files rendered as HTML | `react-markdown` + `remark-gfm`. Fetch raw markdown text, render as React elements. |
| UIUX-01 | Dark mode with system preference detection and manual toggle | Tailwind v4 `@custom-variant dark` with `.dark` class on `<html>`. localStorage persistence. `matchMedia('prefers-color-scheme: dark')` for system detection. |
</phase_requirements>

## Standard Stack

### Core (New Dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-syntax-highlighter | ^15.6.1 | Code syntax highlighting in preview modal | De facto React syntax highlighter. PrismLight build keeps bundle small. Inline styles avoid CSS conflicts with Tailwind. |
| @types/react-syntax-highlighter | ^15.5.13 | TypeScript types | Required for TS project |
| react-markdown | ^10.1.0 | Render markdown as React elements | Official remark ecosystem. Safe by default (no dangerouslySetInnerHTML). |
| remark-gfm | ^4.0.1 | GFM extensions (tables, strikethrough, task lists) | Needed for rendering GitHub-style markdown features |

### Existing (Already Installed)
| Library | Version | Purpose |
|---------|---------|---------|
| react | 19.2.4 | UI framework |
| tailwindcss | 4.2.1 | Styling (dark mode via @custom-variant) |
| lucide-react | 0.577.0 | Icons (Search, X, ChevronUp/Down, ChevronLeft/Right, ZoomIn/Out, Sun, Moon, Eye, etc.) |
| fastapi | 0.135.1 | Backend API |
| starlette | 0.52.1 | FileResponse with native Range request support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| react-syntax-highlighter | prism-react-renderer | More control but more boilerplate. react-syntax-highlighter is simpler for modal preview use case. |
| react-markdown | markdown-to-jsx | markdown-to-jsx is smaller but react-markdown has richer plugin ecosystem via unified/remark/rehype. |
| PrismLight build | Full Prism build | Full build includes all 300+ languages (~100KB). PrismLight registers only needed languages. |

**Installation:**
```bash
cd client && npm install react-syntax-highlighter @types/react-syntax-highlighter react-markdown remark-gfm
```

## Architecture Patterns

### Recommended Project Structure (New Files)
```
client/src/
  components/
    SearchBar.tsx          # Full-width search input with debounce
    FilterChips.tsx        # Horizontal pill/chip buttons for type filtering
    SortableHeader.tsx     # Reusable clickable column header with arrow
    PreviewModal.tsx       # Unified preview modal shell (backdrop, close, nav)
    preview/
      ImagePreview.tsx     # Image display with zoom + gallery nav
      VideoPreview.tsx     # HTML5 video player
      AudioPreview.tsx     # HTML5 audio player
      PdfPreview.tsx       # iframe-based PDF viewer
      CodePreview.tsx      # react-syntax-highlighter with PrismLight
      MarkdownPreview.tsx  # react-markdown renderer
      FileInfoPreview.tsx  # Fallback: name, size, type, modified + download
    ThemeToggle.tsx        # Dark mode toggle button (Sun/Moon icon)
  hooks/
    useSearch.ts           # Search query state, debounce, backend search
    useSort.ts             # Sort field + direction state, comparator
    usePreview.ts          # Preview modal state: open/close, current file, gallery index
    useTheme.ts            # Dark mode state, localStorage, matchMedia listener
  types/
    fileCategories.ts      # FileCategory enum, extension-to-category map, category metadata
  utils/
    fileCategories.ts      # getFileCategory(), getCategoryExtensions(), isPreviewable()
server/app/
  routers/files.py         # Add GET /api/files/search and GET /api/files/preview
  services/file_service.py # Add search_files() recursive search function
```

### Pattern 1: File Category Classification (Shared Map)
**What:** Single source of truth mapping file extensions to categories, used by both FilterChips and FileIcon.
**When to use:** Anywhere extension-to-category logic is needed.
**Example:**
```typescript
// client/src/types/fileCategories.ts

export const FileCategory = {
  ALL: "all",
  IMAGES: "images",
  VIDEO: "video",
  AUDIO: "audio",
  DOCUMENTS: "documents",
  TEXT: "text",
  CODE: "code",
  MARKDOWN: "markdown",
  ARCHIVES: "archives",
  EXECUTABLES: "executables",
} as const;

export type FileCategory = (typeof FileCategory)[keyof typeof FileCategory];

// Map every extension to its category.
// Extensions NOT in this map are uncategorized (only visible under "All").
const EXTENSION_CATEGORY_MAP: Record<string, FileCategory> = {
  jpg: FileCategory.IMAGES,
  jpeg: FileCategory.IMAGES,
  png: FileCategory.IMAGES,
  // ... all extensions from CONTEXT.md
};

export function getFileCategory(fileName: string): FileCategory {
  const dotIndex = fileName.lastIndexOf(".");
  if (dotIndex === -1) {
    return FileCategory.ALL;
  }
  const ext = fileName.slice(dotIndex + 1).toLowerCase();
  return EXTENSION_CATEGORY_MAP[ext] ?? FileCategory.ALL;
}
```

### Pattern 2: Sort State with Comparator
**What:** Sort state as `{field, direction}` with a derived comparator function.
**When to use:** FileList table header clicks.
**Example:**
```typescript
// client/src/hooks/useSort.ts

export const SortField = {
  NAME: "name",
  SIZE: "size",
  MODIFIED: "modified",
} as const;

export type SortField = (typeof SortField)[keyof typeof SortField];

export const SortDirection = {
  ASC: "asc",
  DESC: "desc",
} as const;

export type SortDirection = (typeof SortDirection)[keyof typeof SortDirection];

interface SortState {
  field: SortField;
  direction: SortDirection;
}

// Toggle: same field flips direction; new field resets to ASC
function toggleSort(current: SortState, clickedField: SortField): SortState { ... }

// Returns a comparator for Array.sort()
function buildComparator(state: SortState): (a: FileEntry, b: FileEntry) => number { ... }
```

### Pattern 3: Preview Modal with Content Switching
**What:** Single modal shell renders different preview components based on file category.
**When to use:** Any file click that triggers preview.
**Example:**
```typescript
// PreviewModal.tsx -- shell
function PreviewModal({ file, files, currentPath, onClose, onNavigate }: PreviewModalProps) {
  const category = getFileCategory(file.name);
  const previewUrl = `/api/files/preview?path=${encodeURIComponent(fullPath)}`;

  switch (category) {
    case FileCategory.IMAGES:
      return <ImagePreview url={previewUrl} file={file} files={imageFiles} onNavigate={onNavigate} />;
    case FileCategory.VIDEO:
      return <VideoPreview url={previewUrl} file={file} />;
    // ... etc
    default:
      return <FileInfoPreview file={file} onDownload={...} />;
  }
}
```

### Pattern 4: Tailwind v4 Dark Mode with @custom-variant
**What:** CSS-first dark mode config, JS toggle, localStorage persistence, system preference detection.
**When to use:** The entire app. One-time setup.
**Example:**
```css
/* client/src/index.css */
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));
```
```typescript
// client/src/hooks/useTheme.ts
// Initialize in <head> script to prevent FOUC (flash of unstyled content):
// document.documentElement.classList.toggle("dark",
//   localStorage.theme === "dark" ||
//   (!("theme" in localStorage) && window.matchMedia("(prefers-color-scheme: dark)").matches)
// );
```

### Anti-Patterns to Avoid
- **Fetching entire file for preview URL:** Use the backend preview endpoint that serves the file with correct MIME type and `Content-Disposition: inline`. Do not fetch file content into memory as a blob on the client for images/video/PDF.
- **Building custom video streaming:** Starlette 0.52.1 FileResponse handles Range requests natively. Do NOT implement custom byte-range parsing or StreamingResponse for video.
- **Putting all category logic in each component:** Extract the extension-to-category map into a single utility. FileIcon, FilterChips, PreviewModal, and search all need it.
- **Inline dark mode styles:** Use Tailwind `dark:` prefix on all color utilities. Do not maintain a separate CSS file for dark mode colors.
- **Non-debounced search input:** Filtering on every keystroke is fine for client-side (small list), but the backend recursive search MUST be debounced (300ms minimum) to avoid flooding the server.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Syntax highlighting | Custom tokenizer/parser | react-syntax-highlighter PrismLight | 300+ language grammars, battle-tested, inline styles avoid CSS conflicts |
| Markdown rendering | Regex-based MD parser | react-markdown + remark-gfm | XSS-safe, supports GFM tables/strikethrough, React component output |
| Video/audio range requests | Custom byte-range StreamingResponse | Starlette FileResponse (built-in) | Starlette 0.52.1 handles 206 Partial Content, Content-Range, Accept-Ranges automatically |
| MIME type detection | Extension-to-MIME-type map | Python `mimetypes.guess_type()` | Standard library, comprehensive, no extra dependency |
| Dark mode system detection | Custom media query polling | `window.matchMedia("(prefers-color-scheme: dark)")` | Standard API, supports `.addEventListener("change", ...)` for live updates |
| Search debouncing | Custom setTimeout/clearTimeout | useRef + setTimeout pattern (or extract to `useDebounce` hook) | Common pattern, prevents stale closure issues |

**Key insight:** The biggest "don't hand-roll" item is video streaming. Starlette 0.52.1 (already installed) handles HTTP Range requests in FileResponse automatically. The only change needed is a new endpoint that serves files with `Content-Disposition: inline` instead of `attachment`.

## Common Pitfalls

### Pitfall 1: Flash of Wrong Theme (FOUC)
**What goes wrong:** Dark mode preference loads from localStorage after React hydration, causing a visible flash of light mode.
**Why it happens:** React renders before useEffect runs, so the initial render always uses the default theme.
**How to avoid:** Add an inline `<script>` in `index.html` `<head>` that reads localStorage and sets `.dark` class on `<html>` BEFORE any rendering. This runs synchronously.
**Warning signs:** Brief white flash when loading a page that should be dark.

### Pitfall 2: react-syntax-highlighter Bundle Bloat
**What goes wrong:** Importing the full Prism build adds ~100KB+ of language grammars that will never be used.
**Why it happens:** Default import `import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'` includes ALL languages.
**How to avoid:** Use `PrismLight` or `PrismAsyncLight` and register only the ~30 languages defined in CONTEXT.md code category. Import each language individually.
**Warning signs:** Bundle analyzer shows react-syntax-highlighter as the largest dependency.

### Pitfall 3: Preview Endpoint Missing MIME Type
**What goes wrong:** Browser downloads the file instead of displaying it inline, or displays raw binary.
**Why it happens:** Missing or incorrect `Content-Type` header, or `Content-Disposition: attachment` instead of `inline`.
**How to avoid:** Use `mimetypes.guess_type(filename)` for Content-Type. Set `Content-Disposition: inline`. Fall back to `application/octet-stream` only for truly unknown types.
**Warning signs:** Images not rendering, PDFs downloading, video not playing.

### Pitfall 4: Sort Losing Directories-First Convention
**What goes wrong:** Sorting by size or date mixes files and directories randomly.
**Why it happens:** Sort comparator treats all entries equally.
**How to avoid:** Always sort directories before files (directories first), THEN apply the user's sort within each group.
**Warning signs:** Folders appearing between files after sorting.

### Pitfall 5: Gallery Index Drift After Filter
**What goes wrong:** Image gallery next/prev navigates to wrong image or crashes with out-of-bounds index.
**Why it happens:** Gallery index is based on the full file list, but the filtered/sorted list has different indices.
**How to avoid:** Build the gallery list from the currently visible (filtered + sorted) image files. Track gallery by file name, not array index.
**Warning signs:** Clicking "next" in lightbox jumps to unexpected image.

### Pitfall 6: Search Endpoint Path Traversal
**What goes wrong:** Recursive search walks outside the shared folder.
**Why it happens:** `os.walk` or `Path.rglob` follows symlinks or does not validate each discovered path.
**How to avoid:** Reuse `resolve_safe_path` for the search root. Use `Path.rglob("*")` which follows symlinks, so validate each result with `is_relative_to(base_resolved)`.
**Warning signs:** Search results contain paths outside the shared folder.

### Pitfall 7: Tailwind v4 Dark Mode Config Confusion
**What goes wrong:** `dark:` utilities have no effect.
**Why it happens:** Tailwind v4 uses `@custom-variant` in CSS, not `darkMode` in a JS config file. The project has no tailwind.config.js (correct for v4), but the @custom-variant must be added to index.css.
**How to avoid:** Add `@custom-variant dark (&:where(.dark, .dark *));` to `client/src/index.css` right after `@import "tailwindcss"`.
**Warning signs:** Adding `dark:bg-gray-900` has no visible effect.

## Code Examples

### Backend: Preview Endpoint (Inline File Serving)
```python
# server/app/routers/files.py
# Source: FastAPI/Starlette official docs

import mimetypes
from fastapi.responses import FileResponse

@router.get("/files/preview", response_model=None)
def preview_file(path: str = Query(...)) -> Any:
    """Serve a file inline for browser preview.

    Uses FileResponse which natively supports Range requests (Starlette 0.52.1).
    Sets Content-Disposition: inline so browser displays instead of downloading.
    """
    config = get_server_config()
    try:
        file_path = download_file(config.shared_folder, path)
        mime_type, _ = mimetypes.guess_type(file_path.name)
        content_type = mime_type if mime_type is not None else "application/octet-stream"
        encoded_name = quote(file_path.name)
        return FileResponse(
            path=str(file_path),
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename*=UTF-8\'\'{encoded_name}'
            },
        )
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
```

### Backend: Recursive Search Endpoint
```python
# server/app/services/file_service.py

def search_files(base_dir: Path, search_root: str, query: str) -> list[FileEntry]:
    """Recursively search for files matching query in name.

    Walks the directory tree from search_root, returning entries
    whose name contains the query (case-insensitive).
    Each entry's name includes the relative path from search_root.
    """
    root = resolve_safe_path(base_dir, search_root)
    base_resolved = base_dir.resolve()
    query_lower = query.lower()
    results: list[FileEntry] = []

    for item in root.rglob("*"):
        if not item.is_relative_to(base_resolved):
            continue  # skip symlinks escaping base
        if query_lower not in item.name.lower():
            continue
        # Build relative path from base_dir for display
        relative = str(item.relative_to(root))
        item_stat = item.stat()
        is_dir = stat.S_ISDIR(item_stat.st_mode)
        file_type = FileType.DIRECTORY if is_dir else FileType.FILE
        mtime = datetime.fromtimestamp(item_stat.st_mtime, tz=timezone.utc)

        results.append(FileEntry(
            name=relative,
            size=item_stat.st_size,
            size_display=format_file_size(item_stat.st_size),
            type=file_type,
            modified=mtime.isoformat(),
        ))

    return results
```

### Frontend: PrismLight with Registered Languages
```typescript
// client/src/components/preview/CodePreview.tsx
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism/oneDark";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism/oneLight";

// Register only the languages we need (from CONTEXT.md code category)
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import jsx from "react-syntax-highlighter/dist/esm/languages/prism/jsx";
import tsx from "react-syntax-highlighter/dist/esm/languages/prism/tsx";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import go from "react-syntax-highlighter/dist/esm/languages/prism/go";
import rust from "react-syntax-highlighter/dist/esm/languages/prism/rust";
import java from "react-syntax-highlighter/dist/esm/languages/prism/java";
import c from "react-syntax-highlighter/dist/esm/languages/prism/c";
import cpp from "react-syntax-highlighter/dist/esm/languages/prism/cpp";
import ruby from "react-syntax-highlighter/dist/esm/languages/prism/ruby";
import php from "react-syntax-highlighter/dist/esm/languages/prism/php";
import swift from "react-syntax-highlighter/dist/esm/languages/prism/swift";
import kotlin from "react-syntax-highlighter/dist/esm/languages/prism/kotlin";
import scala from "react-syntax-highlighter/dist/esm/languages/prism/scala";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import markup from "react-syntax-highlighter/dist/esm/languages/prism/markup"; // html, xml
import css from "react-syntax-highlighter/dist/esm/languages/prism/css";
import scss from "react-syntax-highlighter/dist/esm/languages/prism/scss";
import yaml from "react-syntax-highlighter/dist/esm/languages/prism/yaml";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import toml from "react-syntax-highlighter/dist/esm/languages/prism/toml";

SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("typescript", typescript);
SyntaxHighlighter.registerLanguage("jsx", jsx);
SyntaxHighlighter.registerLanguage("tsx", tsx);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("go", go);
SyntaxHighlighter.registerLanguage("rust", rust);
SyntaxHighlighter.registerLanguage("java", java);
SyntaxHighlighter.registerLanguage("c", c);
SyntaxHighlighter.registerLanguage("cpp", cpp);
SyntaxHighlighter.registerLanguage("ruby", ruby);
SyntaxHighlighter.registerLanguage("php", php);
SyntaxHighlighter.registerLanguage("swift", swift);
SyntaxHighlighter.registerLanguage("kotlin", kotlin);
SyntaxHighlighter.registerLanguage("scala", scala);
SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("sql", sql);
SyntaxHighlighter.registerLanguage("markup", markup);
SyntaxHighlighter.registerLanguage("css", css);
SyntaxHighlighter.registerLanguage("scss", scss);
SyntaxHighlighter.registerLanguage("yaml", yaml);
SyntaxHighlighter.registerLanguage("json", json);
SyntaxHighlighter.registerLanguage("toml", toml);

// Extension to Prism language name mapping
const EXT_TO_LANGUAGE: Record<string, string> = {
  js: "javascript", ts: "typescript", jsx: "jsx", tsx: "tsx",
  py: "python", go: "go", rs: "rust", java: "java",
  c: "c", cpp: "cpp", h: "c", hpp: "cpp",
  rb: "ruby", php: "php", swift: "swift", kt: "kotlin", scala: "scala",
  sh: "bash", bash: "bash", zsh: "bash",
  sql: "sql", html: "markup", xml: "markup",
  css: "css", scss: "scss",
  yaml: "yaml", yml: "yaml", json: "json", toml: "toml",
};
```

### Frontend: Tailwind v4 Dark Mode Setup
```css
/* client/src/index.css */
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));
```
```html
<!-- client/index.html -- inline script in <head> to prevent FOUC -->
<script>
  document.documentElement.classList.toggle(
    "dark",
    localStorage.theme === "dark" ||
      (!("theme" in localStorage) &&
        window.matchMedia("(prefers-color-scheme: dark)").matches)
  );
</script>
```
```typescript
// client/src/hooks/useTheme.ts
import { useCallback, useEffect, useState } from "react";

export const ThemeMode = {
  LIGHT: "light",
  DARK: "dark",
  SYSTEM: "system",
} as const;

export type ThemeMode = (typeof ThemeMode)[keyof typeof ThemeMode];

function getEffectiveDark(mode: ThemeMode): boolean {
  if (mode === ThemeMode.LIGHT) return false;
  if (mode === ThemeMode.DARK) return true;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function useTheme(): { mode: ThemeMode; isDark: boolean; setMode: (mode: ThemeMode) => void } {
  // Read initial mode from localStorage
  const stored = localStorage.getItem("theme") as ThemeMode | null;
  const initial: ThemeMode = stored === ThemeMode.LIGHT || stored === ThemeMode.DARK
    ? stored
    : ThemeMode.SYSTEM;

  const [mode, setModeState] = useState<ThemeMode>(initial);
  const isDark = getEffectiveDark(mode);

  // Sync .dark class on <html>
  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  // Listen for system preference changes when in SYSTEM mode
  useEffect(() => {
    if (mode !== ThemeMode.SYSTEM) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      document.documentElement.classList.toggle("dark", mq.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mode]);

  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    if (newMode === ThemeMode.SYSTEM) {
      localStorage.removeItem("theme");
    } else {
      localStorage.setItem("theme", newMode);
    }
  }, []);

  return { mode, isDark, setMode };
}
```

### Frontend: Markdown Preview
```typescript
// client/src/components/preview/MarkdownPreview.tsx
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownPreviewProps {
  content: string;
}

function MarkdownPreview({ content }: MarkdownPreviewProps) {
  return (
    <div className="prose dark:prose-invert max-w-none p-4 overflow-auto">
      <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom Range request handler in FastAPI | Starlette FileResponse has native Range support | Starlette ~0.30+ (refined in 0.49.1 security fix) | No custom streaming code needed for video/audio |
| `tailwind.config.js` darkMode key | `@custom-variant dark (...)` in CSS file | Tailwind CSS v4.0 (2025) | CSS-first config; no JS config file |
| `react-syntax-highlighter` full import | PrismLight or PrismAsyncLight with registerLanguage | Available since v15.0+ | Dramatically smaller bundle |
| `dangerouslySetInnerHTML` for markdown | react-markdown v10 with remark/rehype plugins | react-markdown v9+ | XSS-safe by default |

**Deprecated/outdated:**
- Tailwind `darkMode: 'class'` in JS config: does not exist in Tailwind v4. Must use `@custom-variant` in CSS.
- `rehype-raw` for markdown HTML: not needed unless the markdown files contain embedded raw HTML tags, which is unlikely for code file previews.

## Open Questions

1. **Code preview: text file size limit**
   - What we know: Fetching very large code files (>1MB) as text will be slow and may freeze the browser during syntax highlighting.
   - What's unclear: What is a reasonable size limit before showing a "file too large to preview" message?
   - Recommendation: Set a 500KB limit for code/text/markdown preview. Show file info + download button for larger files.

2. **Image zoom interaction model**
   - What we know: User wants zoom in lightbox.
   - What's unclear: Click-to-zoom-in? Pinch-to-zoom? Scroll-to-zoom? Zoom levels (fit, 100%, 200%)?
   - Recommendation: Click toggles between fit-to-modal and actual-size (100%). Simple, no extra library needed. CSS `object-fit: contain` for fit, `object-fit: none` for actual size.

3. **Search results: how to handle file clicks**
   - What we know: Recursive search results show relative paths from current folder.
   - What's unclear: Should clicking a search result navigate to its parent folder, or open preview directly?
   - Recommendation: Clicking opens preview modal directly. The "Open in new tab" button in the modal serves as the full-view escape hatch. Relative path display tells user where the file lives.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest server/tests/ -x -q` |
| Full suite command | `uv run pytest server/tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-01 | Search endpoint returns matching files recursively | integration | `uv run pytest server/tests/test_search.py -x` | No -- Wave 0 |
| SRCH-01 | Client-side filter reduces visible file list | manual-only | Browser test: type in search bar, verify list filters | N/A |
| SRCH-02 | Filter by type category returns correct files | unit | `uv run pytest server/tests/test_file_service.py::test_search_files -x` | No -- Wave 0 |
| SRCH-03 | Sort by name/size/modified works correctly | manual-only | Browser test: click column headers | N/A |
| MEDP-01 | Image preview serves correct MIME type inline | integration | `uv run pytest server/tests/test_preview.py::test_image_preview -x` | No -- Wave 0 |
| MEDP-02 | Video preview supports Range requests (206) | integration | `uv run pytest server/tests/test_preview.py::test_range_request -x` | No -- Wave 0 |
| MEDP-03 | PDF preview serves inline with correct MIME type | integration | `uv run pytest server/tests/test_preview.py::test_pdf_preview -x` | No -- Wave 0 |
| MEDP-04 | Code file served as text for highlighting | integration | `uv run pytest server/tests/test_preview.py::test_code_preview -x` | No -- Wave 0 |
| MEDP-05 | Markdown file served as text for rendering | integration | `uv run pytest server/tests/test_preview.py::test_markdown_preview -x` | No -- Wave 0 |
| UIUX-01 | Dark mode toggle | manual-only | Browser test: toggle dark mode, verify colors change | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/ -x -q`
- **Per wave merge:** `uv run pytest server/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_search.py` -- covers SRCH-01, SRCH-02 (search endpoint + recursive search service)
- [ ] `server/tests/test_preview.py` -- covers MEDP-01 through MEDP-05 (preview endpoint, MIME types, Range requests)
- [ ] Extend `server/tests/conftest.py` -- add sample image/video/code/markdown files to tmp_shared_folder fixture

## Sources

### Primary (HIGH confidence)
- Starlette 0.52.1 installed in project -- verified FileResponse Range request support via `uv pip show starlette`
- [Starlette Responses docs](https://starlette.dev/responses/) -- FileResponse supports Accept-Ranges: bytes, 206 Partial Content
- [Tailwind CSS v4 Dark Mode docs](https://tailwindcss.com/docs/dark-mode) -- @custom-variant CSS syntax, localStorage pattern, system preference detection
- [react-syntax-highlighter GitHub](https://github.com/react-syntax-highlighter/react-syntax-highlighter) -- PrismLight, registerLanguage, available Prism styles
- [react-markdown GitHub](https://github.com/remarkjs/react-markdown) -- v10.1.0, remark-gfm plugin, safe rendering
- [Python mimetypes docs](https://docs.python.org/3/library/mimetypes.html) -- guess_type() for MIME detection

### Secondary (MEDIUM confidence)
- [FastAPI Custom Responses](https://fastapi.tiangolo.com/advanced/custom-response/) -- FileResponse usage patterns
- [Starlette Range request security fix 0.49.1](https://starlette.dev/release-notes/) -- Range parsing security fix
- [react-markdown NPM](https://www.npmjs.com/package/react-markdown) -- v10.1.0 latest, remark-gfm v4.0.1

### Tertiary (LOW confidence)
- [FastAPI video streaming discussion #7718](https://github.com/fastapi/fastapi/discussions/7718) -- community patterns (but Starlette's built-in support supersedes these)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified on npm/PyPI, versions confirmed, import paths verified
- Architecture: HIGH -- patterns follow existing codebase conventions (as const enums, hooks, component structure, router-per-domain)
- Pitfalls: HIGH -- FOUC, bundle bloat, Range requests are well-documented issues with known solutions
- Dark mode: HIGH -- Tailwind v4 docs explicitly document the @custom-variant approach; confirmed v4.2.1 installed
- Video streaming: HIGH -- Starlette 0.52.1 confirmed installed, Range support is documented in official Starlette docs

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable ecosystem, no fast-moving dependencies)
