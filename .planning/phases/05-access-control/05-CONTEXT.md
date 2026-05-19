# Phase 5: Access Control - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Server operator can restrict access and write operations via CLI flags (`--password`, `--read-only`, `--receive`), and clients see the appropriate gated or limited UI. Password protection gates all access behind a login form. Read-only mode hides all write controls and blocks write API calls. Receive mode shows only a minimal upload-only drop box interface. `--read-only --receive` is rejected at CLI level.

</domain>

<decisions>
## Implementation Decisions

### Drop box (receive mode) layout
- Centered drop zone layout — big dashed-border area with icon + "Drop files here" text, file picker button below
- Inline success list below the drop zone — completed files appear with checkmark, name, and size; list grows as more files are uploaded
- Show server/host machine name in header (not folder path) — uploader knows which server they're sending to
- Inherit the app's existing dark/light/system theme toggle — consistent with the rest of the server UI

### Mode indicators
- Subtle header pill badges next to "Network File Server" title
- Text pills with color coding: "Read Only" (amber), "🔒 Protected" (blue)
- Receive mode needs no badge — the entire drop box UI IS the indicator
- Normal mode (no flags) shows no badge
- When password + read-only are combined, show both badges side by side: [🔒 Protected] [Read Only]
- Server operator's terminal startup banner also prints active modes alongside QR code and URL

### Claude's Discretion
- Login page design — full-page form, visual style, wrong password behavior
- Read-only UI presentation — how write controls are hidden, API rejection behavior
- Exact badge pill styling, colors, and dark mode variants
- Loading and error states for login and drop box
- Session cookie implementation details (itsdangerous pattern already decided)

</decisions>

<specifics>
## Specific Ideas

- Drop box mockup shows the centered dashed drop zone with "Choose files..." button and uploaded file list below
- Mode badge mockup: `Network File Server  [🔒 Protected] [Read Only]` — both badges visible simultaneously when combined
- Drop box header shows machine hostname (e.g., "Rahul's MacBook Pro") for server identification without exposing folder path

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `UploadOverlay` + `UploadPanel` + `useDragDrop` + `useUpload`: Existing drag-and-drop upload infrastructure can be reused in drop box mode
- `useTheme` + `ThemeToggle`: Theme system already handles system/dark/light — drop box page can inherit directly
- `Toast` + `ToastContainer` + `useToast`: Notification system available for upload feedback
- `ConnectionStatus`: WebSocket connection indicator already in header — drop box could optionally show it

### Established Patterns
- `ServerConfig` in `config.py`: Global config with validation — extend with password, read_only, receive fields
- `_build_parser()` in `cli.py`: argparse setup — add `--password`, `--read-only`, `--receive` flags
- Router-level request handling: Write endpoints in `files.py` (upload, rename, delete, create-folder), `clipboard.py`, `file_requests.py` — all need blocking in read-only mode
- `create_app()` in `main.py`: Middleware chain — add auth middleware here

### Integration Points
- 8 write surfaces to block in read-only: POST `/api/files/upload`, PATCH `/api/files/rename`, DELETE `/api/files`, POST `/api/folders`, clipboard write endpoints, file request endpoints, WebSocket snippet updates
- `App.tsx` conditionally renders write controls (Toolbar, BatchToolbar, FileRow actions) — needs server mode prop
- `/api/server-info` endpoint can expose current mode to frontend
- SPA catch-all route in `main.py` — login page and drop box page need routing consideration

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-access-control*
*Context gathered: 2026-03-10*
