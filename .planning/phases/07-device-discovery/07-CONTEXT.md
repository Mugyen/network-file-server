# Phase 7: Device Discovery - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Real-time panel showing connected devices with type, status, and self-identification. Users see who is connected, what device type they're using, when they connected, and which one is "me." Covers DISC-01 through DISC-04. No mDNS/Bonjour network discovery (that's DISC-05/06, deferred to v2+).

</domain>

<decisions>
## Implementation Decisions

### Device panel layout and placement
- Slide-out panel from header button — same pattern as ShareLinksPanel from Phase 6
- Header button shows device count badge (already have `device_count` WebSocket messages)
- Panel lists each device as a card/row: device name, IP address, device type icon, connection duration, "You" badge for self
- Connection duration shows relative time ("connected 5m ago") that updates live
- Empty state: "No other devices connected" when only the current user is present

### Device type detection
- Parse User-Agent header from WebSocket upgrade request to determine device type (phone/laptop/tablet/desktop)
- Simple heuristic — match "Mobile"/"Android"/"iPhone" for phone, "iPad"/"Tablet" for tablet, else laptop/desktop
- Display as icon (no text label needed) — phone, laptop, tablet icons from lucide-react (already in project)
- Unknown/unrecognizable User-Agent defaults to laptop/desktop icon

### Real-time updates
- Extend existing WebSocket `device_connected` / `device_disconnected` toast messages to include full device info (name, IP, device type, connected_at)
- New WebSocket message type `device_list` sent to newly connecting clients with current device roster
- Frontend listens for connect/disconnect events and updates panel state in real time — no polling
- Reuse existing ConnectionManager — extend with IP, User-Agent, and connected_at tracking per device

### Self-identification ("You" badge)
- Client knows its own `device_id` (generated at WebSocket connect time) — compare against device list to mark "You"
- "You" badge is a small pill/tag next to the device name — similar to mode badges from Phase 5
- Own device always sorted to top of the list

### Claude's Discretion
- Exact User-Agent parsing heuristic implementation
- Device card/row visual styling and spacing
- Animation for device connect/disconnect transitions
- Whether to show device's browser name (Chrome, Safari, Firefox) alongside device type
- Connection duration update interval (every second vs every minute)

</decisions>

<specifics>
## Specific Ideas

- Device panel follows the same slide-out pattern as ShareLinksPanel — toggled from header button with count badge
- "You" badge should use the same pill styling as mode badges (Read Only / Protected) from Phase 5
- Connection duration should feel live — "just now", "2m", "15m", "1h 23m" — not stale timestamps

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ConnectionManager` in `connection_manager.py`: Already tracks `device_id`, `device_name`, `active_connections`. Needs extension for IP, User-Agent, connected_at
- `device_count` WebSocket message: Already broadcast on connect/disconnect — extend or add parallel `device_list` message
- `ShareLinksPanel` component: Slide-out panel pattern with header toggle button — reuse for Devices panel
- `ModeBadges` component: Pill badge styling — reuse for "You" badge
- `ToastType` enum: Already has `DEVICE_CONNECTED`/`DEVICE_DISCONNECTED` — extend or add new message types

### Established Patterns
- WebSocket message routing in `websocket.py`: `data.get("type")` switch pattern
- Module-level singleton: `manager = ConnectionManager()` — extend the existing class, don't create a new service
- Panel toggle via header button: ShareLinksPanel toggled via state in App.tsx

### Integration Points
- `websocket_endpoint()` in `websocket.py`: Capture `websocket.client.host` for IP and `websocket.headers["user-agent"]` for device type at connect time
- `ConnectionManager.connect()`: Add parameters for IP, user_agent, connected_at
- `App.tsx` header: Add Devices button alongside Share Links button
- WebSocket client in `main.tsx`: Already connects with `device_name` — receives `device_id` and `device_list` on connect

</code_context>

<deferred>
## Deferred Ideas

- mDNS/Bonjour network broadcast (DISC-05) — deferred to v2+ per REQUIREMENTS.md
- Auto-discover other Network File Server instances (DISC-06) — deferred to v2+
- Device activity tracking (last file accessed, upload/download stats) — v2+ feature
- Device blocking/kicking — would need auth integration, out of scope

</deferred>

---

*Phase: 07-device-discovery*
*Context gathered: 2026-03-10*
