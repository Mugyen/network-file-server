# Phase 7: Device Discovery - Research

**Researched:** 2026-03-10
**Domain:** WebSocket real-time device tracking, User-Agent parsing, React slide-out panel
**Confidence:** HIGH

## Summary

This phase extends the existing WebSocket infrastructure to expose a "Devices" panel showing all connected clients in real time. The backend (`ConnectionManager`) already tracks `device_id` and `device_name` per connection; it needs extension with IP address, User-Agent string, and `connected_at` timestamp. The frontend needs a new `DevicesPanel` slide-out component (same pattern as `ShareLinksPanel`) and a new WebSocket message type `device_list` to bootstrap the panel on connect.

The scope is narrow and well-defined: extend existing server-side tracking, add 1-2 new WS message types, parse User-Agent for device type icons, and render a slide-out panel with self-identification. No new dependencies are required -- lucide-react already has device icons, and User-Agent parsing is simple string matching (no library needed for the heuristic described in CONTEXT.md).

**Primary recommendation:** Extend `ConnectionManager` with per-device metadata (IP, user_agent, connected_at), add a `device_list` WS message sent on connect, and build `DevicesPanel` following the established `ShareLinksPanel` slide-out pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Slide-out panel from header button -- same pattern as ShareLinksPanel from Phase 6
- Header button shows device count badge (already have `device_count` WebSocket messages)
- Panel lists each device as a card/row: device name, IP address, device type icon, connection duration, "You" badge for self
- Connection duration shows relative time ("connected 5m ago") that updates live
- Empty state: "No other devices connected" when only the current user is present
- Parse User-Agent header from WebSocket upgrade request to determine device type (phone/laptop/tablet/desktop)
- Simple heuristic -- match "Mobile"/"Android"/"iPhone" for phone, "iPad"/"Tablet" for tablet, else laptop/desktop
- Display as icon (no text label needed) -- phone, laptop, tablet icons from lucide-react
- Unknown/unrecognizable User-Agent defaults to laptop/desktop icon
- Extend existing WebSocket `device_connected` / `device_disconnected` toast messages to include full device info (name, IP, device type, connected_at)
- New WebSocket message type `device_list` sent to newly connecting clients with current device roster
- Frontend listens for connect/disconnect events and updates panel state in real time -- no polling
- Reuse existing ConnectionManager -- extend with IP, User-Agent, and connected_at tracking per device
- Client knows its own `device_id` (generated at WebSocket connect time) -- compare against device list to mark "You"
- "You" badge is a small pill/tag next to the device name -- similar to mode badges from Phase 5
- Own device always sorted to top of the list

### Claude's Discretion
- Exact User-Agent parsing heuristic implementation
- Device card/row visual styling and spacing
- Animation for device connect/disconnect transitions
- Whether to show device's browser name (Chrome, Safari, Firefox) alongside device type
- Connection duration update interval (every second vs every minute)

### Deferred Ideas (OUT OF SCOPE)
- mDNS/Bonjour network broadcast (DISC-05) -- deferred to v2+ per REQUIREMENTS.md
- Auto-discover other WiFi File Server instances (DISC-06) -- deferred to v2+
- Device activity tracking (last file accessed, upload/download stats) -- v2+ feature
- Device blocking/kicking -- would need auth integration, out of scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DISC-01 | User can view a panel showing all connected devices with name, IP, and connection duration | Extend ConnectionManager with IP/connected_at; new DevicesPanel slide-out component; `device_list` WS message for bootstrap |
| DISC-02 | User sees device type icons (phone/laptop/tablet) parsed from User-Agent | Capture User-Agent from WebSocket upgrade headers; simple string-match heuristic; lucide-react Smartphone/Laptop/Tablet icons |
| DISC-03 | User sees real-time updates when devices connect or disconnect | Extend `device_connected`/`device_disconnected` toast messages with full device info; frontend listens and updates state |
| DISC-04 | User sees a "You" indicator for their own device in the device list | Server sends `device_id` to client on connect; client compares against device list; pill badge styling from ModeBadges |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | WebSocket endpoint | Already used; provides `WebSocket.client.host` and `WebSocket.headers` |
| React | 19.2 | Frontend UI | Already used |
| lucide-react | 0.577 | Device type icons | Already used throughout; has Smartphone, Laptop, Tablet, Monitor icons |
| Tailwind CSS | (project) | Styling | Already used for all components |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | - | - | No new dependencies needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual UA parsing | ua-parser-js | Overkill for 3-category heuristic (phone/tablet/desktop); adds dependency for ~10 lines of code |
| Manual UA parsing (Python) | user-agents library | Same -- too heavy for simple classification |

**No installation needed -- all dependencies are already present.**

## Architecture Patterns

### Backend Changes

#### ConnectionManager Extension
**What:** Add `device_ips`, `device_user_agents`, `device_connected_at` dictionaries alongside existing `active_connections` and `device_names`. Add a `get_device_list()` method returning all device metadata.
**Why:** Keeps the module-level singleton pattern. No new service classes needed.

```python
# Existing pattern in connection_manager.py
class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.device_names: dict[str, str] = {}
        # NEW fields:
        self.device_ips: dict[str, str] = {}
        self.device_user_agents: dict[str, str] = {}
        self.device_connected_at: dict[str, str] = {}  # ISO 8601 timestamps
```

**Alternative (cleaner):** Use a single `device_info: dict[str, DeviceInfo]` with a dataclass/TypedDict instead of parallel dicts. This is preferred for maintainability.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    device_name: str
    ip_address: str
    user_agent: str
    device_type: str  # "phone" | "tablet" | "desktop"
    connected_at: str  # ISO 8601

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.devices: dict[str, DeviceInfo] = {}
```

#### WebSocket Endpoint Extension
**What:** Capture IP and User-Agent at connect time; send `device_list` to new client; include device info in connect/disconnect broadcasts.

```python
# In websocket.py websocket_endpoint():
ip_address = websocket.client.host if websocket.client else "unknown"
user_agent = websocket.headers.get("user-agent", "")
device_type = parse_device_type(user_agent)
connected_at = datetime.now(timezone.utc).isoformat()
```

#### Device Type Parsing
**What:** Simple function to classify User-Agent into phone/tablet/desktop.

```python
from server.app.models.enums import DeviceType

def parse_device_type(user_agent: str) -> DeviceType:
    ua_lower = user_agent.lower()
    # Tablet check first (iPad contains "mobile" in some versions)
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return DeviceType.TABLET
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return DeviceType.PHONE
    return DeviceType.DESKTOP
```

#### New WS Message Types
| Message Type | Direction | When | Payload |
|-------------|-----------|------|---------|
| `device_list` | server -> client | On new client connect | `{ type: "device_list", devices: [...], your_device_id: "..." }` |
| `device_connected` (extended) | server -> others | On client connect | `{ type: "toast", toast_type: "device_connected", ..., device_info: {...} }` |
| `device_disconnected` (extended) | server -> all | On client disconnect | `{ type: "toast", toast_type: "device_disconnected", ..., device_id: "..." }` |

**Key design choice:** The `device_list` message includes `your_device_id` so the client knows which device is "self" without needing a separate message.

### Frontend Changes

#### DevicesPanel Component
**What:** Slide-out panel matching `ShareLinksPanel` pattern.
**Key differences from ShareLinksPanel:**
- State is WebSocket-driven (not fetched from REST API)
- No loading/error states needed (data comes from WS)
- Live-updating connection duration
- Self-identification with "You" badge

#### State Management
**What:** Device list state managed via `useWebSocket` message handlers in `App.tsx`.

```typescript
// New state in App.tsx
const [devices, setDevices] = useState<DeviceInfo[]>([]);
const [myDeviceId, setMyDeviceId] = useState<string>("");

// Register handlers for device_list, device_connected, device_disconnected
```

#### Connection Duration Display
**What:** Format `connected_at` as relative time ("just now", "2m", "15m", "1h 23m").
**Recommendation:** Update every 30 seconds via `setInterval` -- balances between freshness and performance. "Just now" for < 60s, then minutes, then hours+minutes.

### Recommended Project Structure (changes only)

```
server/app/
  models/enums.py           # Add DeviceType enum
  services/
    connection_manager.py   # Add DeviceInfo dataclass, extend ConnectionManager
    device_service.py       # parse_device_type() function (or inline in connection_manager)
  routers/websocket.py      # Capture IP/UA, send device_list, extend toasts

client/src/
  types/websocket.ts        # Add DeviceInfo interface, device_list message type, DeviceType enum
  components/
    DevicesPanel.tsx         # New slide-out panel
    DeviceCard.tsx           # Individual device row (optional -- could be inline)
  hooks/
    useDevices.ts            # Optional: extract device state management from App.tsx
```

### Anti-Patterns to Avoid
- **Polling for device list:** The whole point is real-time via WebSocket. Never use REST polling.
- **Creating a separate WebSocket connection for devices:** Reuse the existing single WS connection.
- **Storing device_id in server-side sessions:** device_id is ephemeral, generated per WS connection. Not a persistent identity.
- **Complex UA parsing library:** A 3-category heuristic does not justify a dependency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Device type icons | Custom SVGs | lucide-react Smartphone/Laptop/Tablet | Already in project, consistent styling |
| Slide-out panel | New panel pattern | Copy ShareLinksPanel structure | Established UX pattern, same backdrop/transition |
| "You" badge | New badge component | Reuse ModeBadges pill styling | Consistent visual language |
| Relative time formatting | Date library (dayjs, date-fns) | Simple custom function (~15 lines) | Only need "Xm" / "Xh Ym" format, no i18n needed |

**Key insight:** This phase is almost entirely wiring existing patterns together. The ShareLinksPanel, ModeBadges, and ConnectionManager are the templates. Very little novel UI or architecture.

## Common Pitfalls

### Pitfall 1: WebSocket.client is None
**What goes wrong:** `websocket.client` can be `None` in test environments or behind certain proxies.
**Why it happens:** Starlette's `WebSocket.client` property depends on the ASGI server providing `client` in the scope.
**How to avoid:** Always use `websocket.client.host if websocket.client else "unknown"` -- never assume non-None.
**Warning signs:** Tests crash with `AttributeError: 'NoneType' object has no attribute 'host'`.

### Pitfall 2: Race Condition on Device List
**What goes wrong:** New client connects, receives `device_list`, but misses a `device_connected` event from another near-simultaneous connection.
**Why it happens:** Between building the device list and sending it, another client might connect.
**How to avoid:** This is acceptable for a LAN tool -- the next connect/disconnect event will correct the list. Don't over-engineer with locks.
**Warning signs:** Device count in header badge doesn't match device list length.

### Pitfall 3: Stale Connection Duration
**What goes wrong:** Connection duration shows wrong time or never updates.
**Why it happens:** `setInterval` cleanup not handled properly, or `connected_at` sent as local time vs UTC.
**How to avoid:** Always use UTC ISO 8601 for `connected_at`. Use `useEffect` cleanup for interval. Calculate duration from `Date.now() - new Date(connected_at).getTime()`.
**Warning signs:** Duration jumps or shows negative values.

### Pitfall 4: Device ID Not Available to Client
**What goes wrong:** Client can't identify "self" in the device list because `device_id` is generated server-side.
**Why it happens:** Current code generates `device_id` in `websocket_endpoint()` but never sends it back to the connecting client.
**How to avoid:** Include `your_device_id` in the `device_list` response sent to the newly connecting client.
**Warning signs:** No "You" badge appears on any device.

### Pitfall 5: Disconnect Cleanup Incomplete
**What goes wrong:** Disconnected devices stay in the device list.
**Why it happens:** `ConnectionManager.disconnect()` must clean up all new fields (device info), not just `active_connections` and `device_names`.
**How to avoid:** If using a single `devices` dict (recommended), cleanup is automatic -- one `pop()` handles everything.
**Warning signs:** Ghost devices in the panel that never go away.

### Pitfall 6: Existing Tests Break
**What goes wrong:** `ConnectionManager.connect()` signature changes break all existing tests.
**Why it happens:** Adding required parameters (ip, user_agent) to `connect()` breaks callers.
**How to avoid:** Either add the new parameters with clear defaults in tests, or update all test call sites. Since project rules say no default parameters, update all callers.
**Warning signs:** `TypeError: connect() missing required argument` in test suite.

## Code Examples

### Backend: Extended ConnectionManager

```python
# Source: Existing connection_manager.py pattern + CONTEXT.md requirements
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from fastapi import WebSocket
from server.app.models.enums import DeviceType


def parse_device_type(user_agent: str) -> DeviceType:
    """Classify User-Agent into device type category."""
    ua_lower = user_agent.lower()
    if "ipad" in ua_lower or "tablet" in ua_lower:
        return DeviceType.TABLET
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return DeviceType.PHONE
    return DeviceType.DESKTOP


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    device_name: str
    ip_address: str
    device_type: str  # DeviceType.value
    connected_at: str  # ISO 8601 UTC


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.devices: dict[str, DeviceInfo] = {}

    async def connect(
        self,
        websocket: WebSocket,
        device_id: str,
        device_name: str,
        ip_address: str,
        user_agent: str,
    ) -> None:
        await websocket.accept()
        self.active_connections[device_id] = websocket
        device_type = parse_device_type(user_agent)
        self.devices[device_id] = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            ip_address=ip_address,
            device_type=device_type.value,
            connected_at=datetime.now(timezone.utc).isoformat(),
        )

    def disconnect(self, device_id: str) -> None:
        self.active_connections.pop(device_id, None)
        self.devices.pop(device_id, None)

    def get_device_name(self, device_id: str) -> str:
        if device_id not in self.devices:
            raise KeyError(f"Device {device_id} not found")
        return self.devices[device_id].device_name

    def get_device_list(self) -> list[dict]:
        return [asdict(info) for info in self.devices.values()]

    def device_count(self) -> int:
        return len(self.active_connections)
```

### Backend: device_list Message

```python
# Source: Existing websocket.py broadcast pattern
def _make_device_list(your_device_id: str) -> dict:
    return {
        "type": "device_list",
        "devices": manager.get_device_list(),
        "your_device_id": your_device_id,
    }

# In websocket_endpoint, after connect:
await manager.send_to(device_id, _make_device_list(device_id))
```

### Frontend: DeviceInfo Type

```typescript
// Source: Matching backend DeviceInfo dataclass
export const DeviceType = {
  PHONE: "phone",
  TABLET: "tablet",
  DESKTOP: "desktop",
} as const;

export type DeviceType = (typeof DeviceType)[keyof typeof DeviceType];

export interface DeviceInfo {
  device_id: string;
  device_name: string;
  ip_address: string;
  device_type: DeviceType;
  connected_at: string; // ISO 8601
}

export interface WSDeviceListPayload {
  type: "device_list";
  devices: DeviceInfo[];
  your_device_id: string;
}
```

### Frontend: Connection Duration Formatter

```typescript
// Source: Custom implementation matching CONTEXT.md "just now", "2m", "15m", "1h 23m"
function formatDuration(connectedAt: string): string {
  const elapsedMs = Date.now() - new Date(connectedAt).getTime();
  const totalMinutes = Math.floor(elapsedMs / 60000);

  if (totalMinutes < 1) {
    return "just now";
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) {
    return `${String(minutes)}m`;
  }
  if (minutes === 0) {
    return `${String(hours)}h`;
  }
  return `${String(hours)}h ${String(minutes)}m`;
}
```

### Frontend: Device Type Icon

```typescript
// Source: lucide-react icons matching CONTEXT.md device types
import { Smartphone, Laptop, Tablet } from "lucide-react";
import { DeviceType } from "../types/websocket.ts";

function DeviceTypeIcon({ deviceType }: { deviceType: DeviceType }): React.ReactElement {
  const className = "h-5 w-5 text-gray-500 dark:text-gray-400";
  switch (deviceType) {
    case DeviceType.PHONE:
      return <Smartphone className={className} />;
    case DeviceType.TABLET:
      return <Tablet className={className} />;
    case DeviceType.DESKTOP:
      return <Laptop className={className} />;
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate `device_names` dict | Single `devices: dict[str, DeviceInfo]` | This phase | Cleaner, single cleanup path |
| `device_count` only on connect | `device_list` + `device_count` on connect | This phase | Clients get full roster |
| No device_id sent to client | `your_device_id` in `device_list` | This phase | Enables self-identification |

**Backward compatibility:** The `device_count` message continues to be broadcast (header badge still uses it). The `device_list` is an addition, not a replacement.

## Open Questions

1. **Should `device_names` dict be removed in favor of `devices` dict?**
   - What we know: `device_names` is only used by `get_device_name()` which is called in the clipboard snippet broadcast. Moving to `devices` dict means `get_device_name()` reads from `devices[device_id].device_name`.
   - What's unclear: Whether removing `device_names` will break anything else.
   - Recommendation: Replace it -- `devices` subsumes `device_names`. Update `get_device_name()` to read from `devices`. This is cleaner and avoids parallel state.

2. **Should extended device info be included in toast messages or only in device_list?**
   - What we know: CONTEXT.md says "extend existing toast messages to include full device info."
   - What's unclear: Whether toast message consumers (ToastContainer) need the extra fields.
   - Recommendation: Add `device_info` to connect/disconnect toasts. The DevicesPanel handler uses it to add/remove from the device list. ToastContainer ignores the extra fields (it only reads `message` and `device_name`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest server/tests/test_websocket.py -x` |
| Full suite command | `uv run pytest server/tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISC-01 | device_list sent on connect with name/IP/duration | integration | `uv run pytest server/tests/test_websocket.py::test_device_list_on_connect -x` | Wave 0 |
| DISC-01 | ConnectionManager.get_device_list() returns all devices | unit | `uv run pytest server/tests/test_websocket.py::test_manager_get_device_list -x` | Wave 0 |
| DISC-02 | parse_device_type classifies phone/tablet/desktop | unit | `uv run pytest server/tests/test_websocket.py::test_parse_device_type -x` | Wave 0 |
| DISC-03 | device_connected toast includes device_info | integration | `uv run pytest server/tests/test_websocket.py::test_device_connected_includes_info -x` | Wave 0 |
| DISC-03 | device_disconnected removes device from list | integration | `uv run pytest server/tests/test_websocket.py::test_device_disconnect_broadcasts_info -x` | Wave 0 |
| DISC-04 | device_list includes your_device_id | integration | `uv run pytest server/tests/test_websocket.py::test_device_list_includes_your_id -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/test_websocket.py -x`
- **Per wave merge:** `uv run pytest server/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New tests in `server/tests/test_websocket.py` -- covers DISC-01 through DISC-04 (extend existing test file)
- [ ] Update existing `test_manager_connect_adds_websocket` and similar tests for new `connect()` signature

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `server/app/services/connection_manager.py` -- current ConnectionManager implementation
- Codebase inspection: `server/app/routers/websocket.py` -- current WebSocket endpoint with connect/disconnect flow
- Codebase inspection: `client/src/hooks/useWebSocket.ts` -- current WS client with message handler pattern
- Codebase inspection: `client/src/components/ShareLinksPanel.tsx` -- slide-out panel pattern to replicate
- Codebase inspection: `client/src/components/ModeBadges.tsx` -- pill badge styling for "You" badge
- Codebase inspection: `client/src/types/websocket.ts` -- WS message type definitions and DeviceName generation
- FastAPI WebSocket docs: `websocket.client.host` for IP, `websocket.headers` for User-Agent

### Secondary (MEDIUM confidence)
- lucide-react icon names (Smartphone, Laptop, Tablet) -- verified from project usage patterns and standard lucide icon set

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all patterns exist in codebase
- Architecture: HIGH - direct extension of existing ConnectionManager and WebSocket patterns
- Pitfalls: HIGH - identified from code inspection (WebSocket.client None, connect signature changes, cleanup)

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no external dependency changes)
