# Phase 4: Real-Time Features - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Connected devices interact in real time via WebSocket: toast notifications for file events and device connections, a shared clipboard scratchpad with named snippets synced live, and a file request system where one device can ask others for specific files. WebSocket infrastructure is shared across all three features.

</domain>

<decisions>
## Implementation Decisions

### Toast notifications
- Position: bottom-right corner of the screen
- Auto-dismiss after 4 seconds; manual dismiss via X button
- Events that trigger toasts on OTHER devices: file uploaded, device connected/disconnected, file request created
- File downloads do NOT trigger toasts (too noisy for batch downloads)
- Stacking: max 3 visible toasts; additional collapse into "+N more notifications" summary
- Each toast shows event type icon, message text, and timestamp

### Clipboard scratchpad
- Lives in a slide-out side panel from the right, toggled via a button in the header
- Panel overlays the file list (does not shrink the file list)
- Multiple named snippets (not a single shared textarea)
- "+" button creates a new snippet card with title field and textarea
- Cards are collapsible; delete via X button
- Real-time character sync across devices (debounced ~300ms via WebSocket)
- Last-write-wins conflict resolution (acceptable for a scratchpad)
- Already decided (PROJECT.md): textarea-based, NOT Clipboard API (HTTPS restriction)

### File request flow
- "Request File" button in the toolbar opens an inline form with description field
- Active requests appear as a banner/card above the file list, visible to all connected devices
- Each banner shows: requester device name, description, "Upload" button, and drag-to-fulfill drop zone
- Fulfillment: both upload button (opens file picker) and drag-and-drop onto the request banner
- After fulfillment: banner updates to "Fulfilled by Device Y: filename" with link to file
- Fulfilled request banner stays visible until the REQUESTER dismisses it (not auto-dismiss)
- Toast notification sent to requester when their request is fulfilled

### Connection status
- Small green/red status dot in the header area (green = connected, red = disconnected)
- Hovering the dot shows tooltip with device count: "3 devices connected"
- Server tracks active WebSocket connections for device count
- On disconnect: automatic reconnection with exponential backoff
- While disconnected: slim banner below header shows "Reconnecting..." with spinner
- File browsing (HTTP) continues to work while WebSocket is disconnected; only real-time features pause

### Data persistence
- Clipboard snippets and file requests persist to disk (JSON file)
- Survive server restarts
- Storage location: a JSON file in the server's data area (not in the shared folder to avoid polluting user files)

### Claude's Discretion
- WebSocket message protocol design (JSON message types, payload structure)
- Reconnection backoff timing and max retry strategy
- Toast animation style (slide in, fade in)
- Scratchpad panel width and resize behavior
- Snippet card UI details (expand/collapse animation, max snippets, character limits)
- File request expiration policy (if any)
- Device identification strategy (random name, browser fingerprint, or user-chosen)
- Persistence file format and location details
- Mobile layout for the scratchpad panel (full-screen overlay vs bottom sheet)

</decisions>

<specifics>
## Specific Ideas

- Toast stacking should feel like VS Code notifications — stacked in corner, not overwhelming
- Scratchpad panel should feel like a Slack sidebar — slides in, overlays content, easy to dismiss
- File request banners should be attention-grabbing but not blocking — like GitHub's "review requested" banner
- Upload button on request banner reuses existing upload infrastructure (XHR with progress)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useUpload` hook: XHR-based upload with progress tracking — reuse for file request fulfillment uploads
- `useDragDrop` hook: Drag-and-drop detection — extend for request banner drop zones
- `UploadOverlay` / `UploadPanel`: Upload UI patterns — file request upload can follow same flow
- `ConfirmDialog` / modal pattern: Backdrop + centered content — scratchpad panel follows similar overlay approach
- `useTheme` hook: Dark mode state — all new components need `dark:` class variants
- `apiFetch<T>`: HTTP client — extend for clipboard and request REST endpoints
- `SearchBar` component: Inline form pattern — request creation form can follow similar inline approach

### Established Patterns
- Pydantic schemas for all API responses (`server/app/models/schemas.py`)
- Router-per-domain pattern — new routers for `clipboard.py`, `requests.py`, `websocket.py`
- `as const` TypeScript enums (FileType, FileCategory, SortField, ThemeMode) — use for WebSocket message types, toast types, request status
- Tailwind CSS v4 with `@custom-variant dark` — all components need dark mode classes
- Hooks for state management (useSearch, useSort, useTheme) — new hooks: useWebSocket, useToast, useClipboard, useFileRequests

### Integration Points
- `server/app/main.py`: Mount WebSocket endpoint and new REST routers
- `client/src/App.tsx`: WebSocket provider, toast container, scratchpad toggle state, request banners above file list
- `client/src/api/`: New modules for clipboard and file request REST endpoints
- `client/src/hooks/`: New hooks for WebSocket, toasts, clipboard, file requests
- Header area: Status dot + scratchpad toggle button + device count tooltip

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-real-time-features*
*Context gathered: 2026-03-09*
