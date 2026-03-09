# Phase 3: Search, Preview, and UI Polish - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can find files quickly via search/filter/sort and preview media content without downloading. Dark mode rounds out the UI. Search is recursive (searches subfolders), filtering is by file type category, sorting is by column headers. Preview uses a unified modal overlay for all file types. Real-time features and clipboard sharing are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Search placement and behavior
- Full-width search bar on its own dedicated row above the toolbar (not inside the toolbar)
- Recursive search into subfolders (requires a backend search endpoint that walks the directory tree)
- Search results display file paths relative to current folder (e.g., `photos/vacation/sunset.jpg`)
- Client-side filtering for current folder; backend endpoint for recursive subfolder search

### Type filter controls
- Horizontal row of toggleable pill/chip buttons below the search bar
- Multi-select: multiple chips can be active simultaneously (show files matching ANY selected type)
- Categories (10 total): All, Images, Video, Audio, Documents, Text, Code, Markdown, Archives, Executables/Binaries
- Text is separate from Documents (Documents = pdf, doc, docx, xls, ppt; Text = txt)
- Markdown is its own category (rendered as HTML, distinct from code)
- No "Other" chip — uncategorized files only appear under "All"

### Sort controls
- Clickable column headers (Name, Size, Modified) with arrow indicator showing sort direction
- Click header to sort; click again to toggle ascending/descending
- Default sort: Name ascending

### Preview modal
- Clicking a file opens a preview modal (pop-up overlay)
- Modal includes an "Open in new tab" button for full-page viewing
- Unified modal pattern for all previewable file types: images, video, audio, PDF, code, markdown
- Image lightbox: gallery with next/prev arrow buttons to navigate between images in the folder; keyboard arrow keys supported; shows "3 of 12" position indicator; download button in modal
- Video/audio: inline player with seeking controls in the modal
- PDF: embedded in iframe using browser's native PDF renderer (zoom, scroll, page navigation built-in)
- Code files: syntax highlighting with line numbers in the modal
- Markdown files: rendered as HTML in the modal
- Non-previewable files: show file info (name, size, type, modified) + download button

### File type category definitions
- **Images**: jpg, jpeg, png, gif, svg, webp, bmp, ico, tiff
- **Video**: mp4, webm, mov, avi, mkv, flv, wmv
- **Audio**: mp3, wav, ogg, flac, aac, m4a, wma
- **Documents**: pdf, doc, docx, xls, xlsx, ppt, pptx, odt, ods, odp
- **Text**: txt, csv, log, ini, cfg, conf, env
- **Code**: js, ts, jsx, tsx, py, go, rs, java, c, cpp, h, hpp, rb, php, swift, kt, scala, sh, bash, zsh, sql, html, css, scss, yaml, yml, json, xml, toml
- **Markdown**: md, mdx
- **Archives**: zip, tar, gz, bz2, xz, rar, 7z, tgz
- **Executables/Binaries**: exe, msi, dmg, app, bin, deb, rpm, apk, elf, out

### Claude's Discretion
- Dark mode: toggle placement, system preference auto-detect, persistence (localStorage), transition animation
- Click interaction model: whether clicking file name directly opens preview, or a separate preview icon in the Actions column
- Video/audio player styling and controls
- Image zoom behavior within the lightbox
- Keyboard shortcuts for preview navigation (Escape to close, etc.)
- Mobile layout for filter chips (scrollable row, wrapping, etc.)
- Search debounce timing and empty state messaging
- Loading states for preview content
- Responsive breakpoints for search bar and chips

</decisions>

<specifics>
## Specific Ideas

- Preview modal should have a clear "Open in new tab" button so users can get a full-page experience when the modal feels too small
- Gallery navigation for images should feel natural — arrow keys, visible next/prev buttons, position indicator ("3 of 12")
- Search results from subfolders must show the relative path so users know where the file lives
- Filter chips should allow multi-select toggle — clicking "Images" then "Video" shows both

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FileList` + `FileRow` components: Table layout with checkbox, Name, Size, Modified, Actions columns — needs sort click handlers on headers
- `Toolbar` component: Currently has Upload + New Folder — search bar goes above this, filter chips between search and toolbar
- `BatchToolbar`: Replaces Toolbar when items selected — search/filter should remain visible even in batch mode
- `ConfirmDialog` / `ConflictDialog`: Modal patterns exist — preview modal can follow similar overlay/backdrop approach
- `FileIcon` component: Maps extensions to Lucide icons — can be extended with category classification
- `FileEntry` type: Has `name`, `size`, `size_display`, `type`, `modified` — sufficient for client-side sort
- `apiFetch<T>`: GET requests to backend — needs search endpoint added
- `usePathNavigation` hook: URL-based navigation via `?path=` — search results may need different URL handling

### Established Patterns
- Pydantic schemas for all API responses (`server/app/models/schemas.py`)
- Router-per-domain pattern (`server/app/routers/files.py`) — search endpoint goes here
- Tailwind CSS v4 with `@tailwindcss/vite` plugin
- Lucide React icons throughout
- `as const` pattern for TypeScript enums (e.g., `FileType`)

### Integration Points
- `server/app/routers/files.py`: New search endpoint (GET `/api/files/search?q=...&path=...`)
- `server/app/services/file_service.py`: Recursive file search function with `resolve_safe_path` for safety
- `client/src/App.tsx`: Search state, filter state, sort state, preview modal state
- `client/src/components/`: New components — SearchBar, FilterChips, PreviewModal, CodePreview, MarkdownPreview
- `client/src/hooks/`: New hooks — useSearch, useSort, usePreview
- Range request support on backend needed for video/audio streaming (flagged in STATE.md)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-search-preview-and-ui-polish*
*Context gathered: 2026-03-09*
