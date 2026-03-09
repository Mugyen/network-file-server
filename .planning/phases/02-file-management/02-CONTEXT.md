# Phase 2: File Management - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Full file management through the browser: upload (drag-and-drop + button), download (individual + ZIP batch), folder navigation with breadcrumbs, rename, delete, create folders, batch operations, responsive mobile layout, and file type icons. Search, preview, and real-time features are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Upload experience
- Full-page drop zone: overlay appears when dragging files over the browser window
- Explicit "Upload" button in toolbar for mobile users and discoverability
- Floating panel (like Google Drive) shows all active uploads with individual progress bars
- On failure: show error state with retry button per file (no auto-retry)
- File name conflicts: prompt user for each conflict (overwrite / rename / skip)

### File browser navigation
- Double-click folder row to navigate into it; single click selects the row
- Breadcrumbs as clickable path segments: Home / photos / vacation / 2024
- URL updates to reflect current path (e.g., /?path=photos/vacation) — enables browser back button and link sharing

### Batch operations
- Checkboxes always visible in a column on the left of each row
- "Select All" checkbox in table header with extended "Select all N items" link (Gmail-style)
- When items selected: header toolbar replaced with batch action bar showing "X selected", Download ZIP, Delete buttons
- Batch delete triggers a centered modal dialog: "Delete N files? This cannot be undone." with Cancel/Delete

### Destructive actions
- Delete confirmation via modal dialog (same pattern for single and batch delete)
- Rename: inline editing (click rename action, name becomes editable text field)

### Claude's Discretion
- File type icon set and mapping strategy (UIUX-03)
- Responsive breakpoints and mobile layout adjustments (UIUX-02)
- "New folder" UI trigger (button in toolbar vs context menu vs both)
- Download individual file behavior (direct browser download vs confirmation)
- Empty folder state messaging
- Exact styling of the upload overlay, floating panel, and modals

</decisions>

<specifics>
## Specific Ideas

- Upload floating panel should feel like Google Drive's upload panel — bottom-right corner, collapsible, shows per-file progress
- Batch selection toolbar replacing the header should feel like Google Drive — contextual actions replace normal toolbar
- File conflict prompt should be per-file, not a blanket "overwrite all" — user retains control per conflict

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apiFetch<T>` in `client/src/api/client.ts`: GET-only currently, needs POST/DELETE/PUT extension for uploads and mutations
- `resolve_safe_path` in `server/app/services/file_service.py`: All new endpoints must route through this for path safety
- `list_directory` in `server/app/services/file_service.py`: Already returns `DirectoryListing` with `FileEntry` objects — extend for navigation
- `FileRow` component: Currently display-only, needs click handlers for selection and double-click navigation
- `FileList` component: Wraps table, needs checkbox column and selection state
- `FileType` enum (`as const` pattern): FILE and DIRECTORY — may need extension for file type icons

### Established Patterns
- Pydantic schemas for all API responses (`server/app/models/schemas.py`)
- Router-per-domain pattern (`server/app/routers/files.py`) — new endpoints go here or in new routers
- `PathTraversalError` / `FileNotFoundError` exception handling in routers
- Tailwind CSS v4 with `@tailwindcss/vite` plugin — no PostCSS config
- `as const` for TypeScript enums (Vite `erasableSyntaxOnly`)

### Integration Points
- `server/app/main.py`: New routers included via `app.include_router()`
- `client/src/api/`: New API modules for upload, delete, rename, folder operations
- `client/src/types/`: New types for upload state, selection state, conflict resolution
- `client/src/App.tsx`: Route/state management for folder navigation with URL sync

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-file-management*
*Context gathered: 2026-03-09*
