# Phase 4: Real-Time Features - Research

**Researched:** 2026-03-09
**Domain:** WebSocket real-time communication, toast notifications, shared clipboard, file request system
**Confidence:** HIGH

## Summary

Phase 4 adds real-time interactivity via WebSocket: toast notifications for file events, a shared clipboard (scratchpad) with named snippets, and a file request system. The existing stack already has everything needed -- FastAPI/Starlette includes native WebSocket support, `websockets 16.0` is already installed via `uvicorn[standard]`, and `aiofiles` is available for async JSON persistence. No new Python dependencies are required. On the client side, the native browser `WebSocket` API is sufficient; no external WebSocket library is needed for React.

The core architectural pattern is a server-side `ConnectionManager` that tracks active WebSocket connections and broadcasts JSON messages to all connected clients. Each feature (toasts, clipboard, file requests) shares the same WebSocket connection per client, differentiated by a `type` field in the JSON message protocol. The server persists clipboard snippets and file requests to a JSON file in a data directory alongside (but outside) the shared folder.

**Primary recommendation:** Build a single WebSocket endpoint at `/ws` with a JSON message protocol using a `type` discriminator field. All three features (notifications, clipboard, file requests) share this connection. Use Pydantic discriminated unions on the server for message validation, and `as const` TypeScript enums on the client for message type safety.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Toast notifications: bottom-right corner, auto-dismiss after 4 seconds, manual dismiss via X, max 3 visible with "+N more" collapse
- Toast triggers on OTHER devices: file uploaded, device connected/disconnected, file request created (NOT file downloads)
- Each toast shows event type icon, message text, and timestamp
- Clipboard scratchpad: slide-out side panel from right, toggled via header button, overlays file list
- Multiple named snippets with "+" button, collapsible cards, delete via X
- Real-time character sync debounced ~300ms via WebSocket, last-write-wins conflict resolution
- Textarea-based, NOT Clipboard API (HTTPS restriction)
- File request: "Request File" button in toolbar opens inline form with description field
- Active requests appear as banner/card above file list, visible to all devices
- Banner shows: requester device name, description, "Upload" button, drag-to-fulfill drop zone
- Fulfillment: both upload button (file picker) and drag-and-drop onto request banner
- After fulfillment: banner updates to "Fulfilled by Device Y: filename" with link to file
- Fulfilled request stays visible until REQUESTER dismisses (not auto-dismiss)
- Toast notification sent to requester when their request is fulfilled
- Connection status: green/red dot in header, tooltip with device count, exponential backoff reconnect
- Disconnected: slim banner below header "Reconnecting..." with spinner; HTTP file browsing continues
- Clipboard snippets and file requests persist to disk (JSON file) outside shared folder

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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RTME-01 | WebSocket connection established on page load | ConnectionManager pattern, useWebSocket hook with auto-connect, Vite WS proxy config |
| RTME-02 | Toast notifications shown for file uploads/downloads | Server broadcasts file events to all OTHER connections, client useToast hook manages stack |
| RTME-03 | Shared text clipboard (scratchpad) synced across all connected devices | Clipboard service with JSON persistence, debounced WS sync at 300ms, last-write-wins |
| RTME-04 | User can create a file request with description visible to all devices | FileRequest model with Pydantic, REST endpoints + WS broadcast, banner UI above file list |
| RTME-05 | User can fulfill a file request by uploading | Reuse existing useUpload/uploadWithProgress, associate upload with request ID, fulfill broadcast |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI WebSocket | 0.135.1 (installed) | WebSocket endpoint | Native support via Starlette, zero extra deps |
| websockets | 16.0 (installed) | ASGI WebSocket protocol | Already installed via uvicorn[standard] |
| aiofiles | 25.1.0 (installed) | Async JSON file persistence | Already used for file uploads, reuse for persistence |
| Pydantic | 2.12.5 (installed) | WebSocket message validation | Already used for all schemas, discriminated unions for WS messages |
| Native WebSocket API | Browser built-in | Client-side WS connection | No library needed; React hook wraps native API |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | 0.577.0 (installed) | Toast icons, status dot, scratchpad icons | All new UI components |
| Tailwind CSS v4 | 4.2.1 (installed) | All styling including animations | Toast slide-in, panel transitions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native WebSocket API | react-use-websocket npm package | Adds dependency; native API is simple enough for this use case |
| In-memory ConnectionManager | encode/broadcaster with Redis | Overkill for single-process LAN tool; adds Redis dependency |
| JSON file persistence | SQLite | Overkill for snippets + requests; JSON is simpler and human-readable |

**Installation:**
No new packages needed. All dependencies already installed.

## Architecture Patterns

### Recommended Project Structure
```
server/app/
  routers/
    websocket.py          # WebSocket endpoint + connection manager
    clipboard.py          # REST endpoints for clipboard CRUD
    file_requests.py      # REST endpoints for file request CRUD
  services/
    connection_manager.py # ConnectionManager class (WS tracking + broadcast)
    clipboard_service.py  # Clipboard snippet CRUD + JSON persistence
    file_request_service.py # File request CRUD + JSON persistence
    persistence.py        # Shared async JSON read/write utility
  models/
    enums.py              # Add WSMessageType, ToastType, RequestStatus enums
    schemas.py            # Add WS message schemas, clipboard/request models

client/src/
  hooks/
    useWebSocket.ts       # WebSocket connection, reconnect, message dispatch
    useToast.ts           # Toast state management (add, dismiss, stack limit)
    useClipboard.ts       # Clipboard snippet state + WS sync
    useFileRequests.ts    # File request state + WS sync
  components/
    ToastContainer.tsx    # Fixed bottom-right container for toast stack
    Toast.tsx             # Individual toast with icon, message, timestamp, dismiss
    ScratchpadPanel.tsx   # Slide-out right panel with snippet cards
    SnippetCard.tsx       # Collapsible card with title + textarea
    FileRequestBanner.tsx # Banner above file list for active requests
    FileRequestForm.tsx   # Inline form for creating a request
    ConnectionStatus.tsx  # Green/red dot + tooltip + reconnecting banner
  api/
    clipboard.ts          # REST calls for clipboard CRUD
    fileRequests.ts       # REST calls for file request CRUD
  types/
    websocket.ts          # WS message types, ToastType, RequestStatus enums
    clipboard.ts          # Snippet type definition
    fileRequests.ts       # FileRequest type definition
```

### Pattern 1: Singleton ConnectionManager
**What:** A server-side class that tracks all active WebSocket connections, assigns device IDs, and broadcasts messages. Single instance shared across the app.
**When to use:** All WebSocket operations go through this manager.
**Example:**
```python
# Source: FastAPI official docs pattern, adapted for this project
from fastapi import WebSocket
from server.app.models.enums import WSMessageType

class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}  # device_id -> ws

    async def connect(self, websocket: WebSocket, device_id: str) -> None:
        await websocket.accept()
        self.active_connections[device_id] = websocket

    def disconnect(self, device_id: str) -> None:
        self.active_connections.pop(device_id, None)

    async def broadcast(self, message: dict, exclude_device: str) -> None:
        """Broadcast to all connections except the sender."""
        for did, ws in list(self.active_connections.items()):
            if did == exclude_device:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                # Connection died -- remove it
                self.active_connections.pop(did, None)

    async def send_to(self, device_id: str, message: dict) -> None:
        """Send to a specific device."""
        ws = self.active_connections.get(device_id)
        if ws is not None:
            await ws.send_json(message)

    def device_count(self) -> int:
        return len(self.active_connections)
```

### Pattern 2: Typed JSON Message Protocol
**What:** All WebSocket messages are JSON with a `type` discriminator field. Server validates with Pydantic discriminated unions. Client uses `as const` TypeScript enums.
**When to use:** Every WebSocket send/receive.
**Example server-side:**
```python
from enum import Enum
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field

class WSMessageType(str, Enum):
    # Server -> Client
    TOAST = "toast"
    SNIPPET_UPDATED = "snippet_updated"
    SNIPPET_CREATED = "snippet_created"
    SNIPPET_DELETED = "snippet_deleted"
    REQUEST_CREATED = "request_created"
    REQUEST_FULFILLED = "request_fulfilled"
    REQUEST_DISMISSED = "request_dismissed"
    DEVICE_COUNT = "device_count"
    # Client -> Server
    SNIPPET_UPDATE = "snippet_update"
    # ... etc

class ToastMessage(BaseModel):
    type: Literal["toast"] = "toast"
    toast_type: str  # "file_uploaded", "device_connected", etc.
    message: str
    device_name: str
    timestamp: str
```

**Example client-side:**
```typescript
// types/websocket.ts
export const WSMessageType = {
  TOAST: "toast",
  SNIPPET_UPDATED: "snippet_updated",
  SNIPPET_CREATED: "snippet_created",
  SNIPPET_DELETED: "snippet_deleted",
  REQUEST_CREATED: "request_created",
  REQUEST_FULFILLED: "request_fulfilled",
  REQUEST_DISMISSED: "request_dismissed",
  DEVICE_COUNT: "device_count",
} as const;
export type WSMessageType = (typeof WSMessageType)[keyof typeof WSMessageType];

interface WSMessage {
  type: WSMessageType;
  [key: string]: unknown;
}
```

### Pattern 3: useWebSocket Hook with Exponential Backoff
**What:** A custom React hook that manages WebSocket lifecycle, reconnects on disconnect, and dispatches messages to registered handlers.
**When to use:** Single hook instantiated once in App.tsx, callbacks registered per feature.
**Example:**
```typescript
// Reconnection: exponential backoff
// Initial: 1s, multiplier: 2x, max: 30s, with jitter
function getReconnectDelay(attempt: number): number {
  const base = Math.min(1000 * Math.pow(2, attempt), 30000);
  const jitter = Math.random() * 1000;
  return base + jitter;
}
```

### Pattern 4: Async JSON Persistence with Atomic Writes
**What:** Server persists clipboard snippets and file requests to a JSON file. Write uses temp file + os.replace for atomicity.
**When to use:** All mutations to persistent state.
**Example:**
```python
import json
import os
import tempfile
import aiofiles
from pathlib import Path

async def write_json_atomic(file_path: Path, data: dict) -> None:
    """Write JSON data atomically: write to temp file, then rename."""
    dir_path = file_path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(dir_path), suffix=".tmp")
    os.close(fd)
    try:
        async with aiofiles.open(tmp_path, "w") as f:
            await f.write(json.dumps(data, indent=2))
        os.replace(tmp_path, str(file_path))
    except Exception:
        os.unlink(tmp_path)
        raise

async def read_json(file_path: Path) -> dict:
    """Read JSON file, returning empty dict if file does not exist."""
    if not file_path.exists():
        return {}
    async with aiofiles.open(file_path, "r") as f:
        content = await f.read()
    return json.loads(content)
```

### Pattern 5: Device Identification via Random Name + localStorage
**What:** On first visit, generate a random device name (e.g., "Blue Falcon", "Red Panda") and store in localStorage. User sees their device name; other devices see it in toasts and file requests.
**Why:** No fingerprinting needed. Simple, friendly, privacy-respecting. Works across HTTP (no crypto.randomUUID).
**Strategy:**
- Generate: pick random adjective + random animal (small dictionaries, ~50 each)
- Store: localStorage key `wfs_device_name`
- Send: include in WebSocket connect handshake as query param `?device_name=Blue+Falcon`
- Reuse: same name persists across page reloads on same browser

### Anti-Patterns to Avoid
- **Single global WebSocket handler in App.tsx:** Use a hook, not inline logic in the component. Keep App.tsx as a composition root.
- **Separate WebSocket per feature:** Use ONE connection per client with message type routing. Multiple connections waste resources.
- **Synchronous file I/O for persistence:** Always use aiofiles. Synchronous writes block the event loop and stall all WebSocket communication.
- **No error handling in broadcast loop:** Always try/except per connection in broadcast. A dead connection must not break broadcast to others.
- **Storing persistent data in the shared folder:** Users would see `.wfs_data.json` in their file browser. Store in a separate data directory.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket protocol | Custom TCP/binary protocol | JSON over native WebSocket API | Browser-native, debuggable, FastAPI has built-in support |
| Message validation | Manual dict parsing | Pydantic discriminated unions | Type safety, auto-validation, consistent with existing codebase |
| Upload progress | New upload mechanism for file requests | Existing `useUpload` hook + `uploadWithProgress` | Already handles XHR progress, conflict resolution, concurrency |
| Drag-and-drop for request fulfillment | New drag handler | Extend existing `useDragDrop` hook | Counter pattern already handles flicker, reuse with targeted drop zones |
| Atomic file writes | Manual open/write/close | tempfile + os.replace pattern | Prevents corruption on crash; os.replace is atomic on same filesystem |
| Reconnection logic | Manual setTimeout chains | Exponential backoff with jitter in useWebSocket | Well-understood algorithm, prevents thundering herd on server restart |

**Key insight:** The existing codebase already has upload infrastructure (XHR progress), drag-drop handling, modal/overlay patterns, and the API client -- all of which should be reused, not rebuilt.

## Common Pitfalls

### Pitfall 1: Stale WebSocket Reference in React Closures
**What goes wrong:** Callbacks registered with `useEffect` capture old `ws` reference after reconnect.
**Why it happens:** React closures capture the WebSocket instance from the render when the effect was created. After reconnect, a new WebSocket is created but old callbacks still reference the closed one.
**How to avoid:** Store WebSocket instance in a `useRef`, not `useState`. Access via `wsRef.current` inside callbacks.
**Warning signs:** Messages stop arriving after a reconnect cycle; send calls silently fail.

### Pitfall 2: Broadcast Failure Cascade
**What goes wrong:** One dead connection in the broadcast loop raises an exception, preventing messages from reaching remaining clients.
**Why it happens:** `await ws.send_json(message)` throws if the connection is already closed. Without try/except per connection, the loop aborts.
**How to avoid:** Wrap each `send_json` in try/except. On exception, remove that connection from active list. Iterate over a copy of the connection list (`list(self.active_connections.items())`).
**Warning signs:** All clients stop receiving updates after one client disconnects ungracefully.

### Pitfall 3: WebSocket Proxy Not Configured in Vite
**What goes wrong:** WebSocket connections fail in development mode because Vite proxy only handles HTTP.
**Why it happens:** Existing Vite config only proxies `/api` via HTTP. WebSocket at `/ws` needs explicit `ws: true` configuration.
**How to avoid:** Add `/ws` proxy entry in `vite.config.ts` with `target: "ws://localhost:8000"` and `ws: true`.
**Warning signs:** WebSocket connects in production (direct to server) but fails in dev (Vite proxy).

### Pitfall 4: Race Condition on Persistence Reads During Concurrent Writes
**What goes wrong:** Two simultaneous snippet updates read stale JSON, both write, second write loses first update.
**Why it happens:** No locking on the JSON file. Two async tasks can interleave read-modify-write.
**How to avoid:** Use an `asyncio.Lock` per persistence file. Acquire lock before read-modify-write cycle.
**Warning signs:** Occasionally lost snippet updates or file requests when multiple devices act simultaneously.

### Pitfall 5: Toast Flooding from Batch Operations
**What goes wrong:** Uploading 20 files generates 20 toast notifications, overwhelming other devices.
**Why it happens:** Each upload triggers a separate toast broadcast.
**How to avoid:** Batch upload notifications: if multiple files uploaded in quick succession from same device, collapse into single toast "Device X uploaded 20 files".
**Warning signs:** Users on other devices get a wall of toasts during batch uploads.

### Pitfall 6: Memory Leak from Uncleared Toast Timeouts
**What goes wrong:** Toast auto-dismiss timers accumulate if toasts are manually dismissed before timeout fires.
**Why it happens:** `setTimeout` created for auto-dismiss but not cleared when toast is manually removed.
**How to avoid:** Track timeout IDs per toast. Clear timeout on manual dismiss and on component unmount.
**Warning signs:** Growing memory usage and unexpected toast disappearances after extended use.

### Pitfall 7: WebSocket Endpoint Must Be Mounted BEFORE SPA Catch-All
**What goes wrong:** WebSocket connections return HTML (the SPA index.html) instead of upgrading to WS.
**Why it happens:** The SPA catch-all route `/{path:path}` in `main.py` matches `/ws` before the WebSocket router gets a chance.
**How to avoid:** Include the WebSocket router BEFORE the SPA catch-all is registered. The existing code registers routers before the catch-all, so follow the same pattern.
**Warning signs:** WebSocket connections immediately close with a non-101 status code.

## Code Examples

### WebSocket Endpoint (Server)
```python
# Source: FastAPI official docs + project conventions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    device_name: str,  # Query param from client
) -> None:
    device_id = generate_device_id()  # e.g. timestamp-based
    await manager.connect(websocket, device_id)

    # Broadcast device connected toast to others
    await manager.broadcast(
        {"type": "toast", "toast_type": "device_connected",
         "message": f"{device_name} connected", "device_name": device_name},
        exclude_device=device_id,
    )
    # Send current device count to all
    await manager.broadcast_all(
        {"type": "device_count", "count": manager.device_count()}
    )

    try:
        while True:
            data = await websocket.receive_json()
            await handle_message(data, device_id, device_name)
    except WebSocketDisconnect:
        manager.disconnect(device_id)
        await manager.broadcast(
            {"type": "toast", "toast_type": "device_disconnected",
             "message": f"{device_name} disconnected", "device_name": device_name},
            exclude_device=device_id,
        )
        await manager.broadcast_all(
            {"type": "device_count", "count": manager.device_count()}
        )
```

### useWebSocket Hook (Client)
```typescript
// Source: Native WebSocket API + exponential backoff pattern
interface UseWebSocketResult {
  isConnected: boolean;
  deviceCount: number;
  sendMessage: (message: object) => void;
  addMessageHandler: (type: string, handler: (data: unknown) => void) => void;
  removeMessageHandler: (type: string) => void;
}

function useWebSocket(deviceName: string): UseWebSocketResult {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [deviceCount, setDeviceCount] = useState<number>(0);
  const handlersRef = useRef<Map<string, (data: unknown) => void>>(new Map());
  const attemptRef = useRef<number>(0);

  // Connect logic with reconnect
  // On message: parse JSON, route by type to registered handler
  // On close: schedule reconnect with exponential backoff
  // Cleanup on unmount: close connection, clear timers
}
```

### Vite WebSocket Proxy Config
```typescript
// vite.config.ts addition
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

### Toast Component Pattern
```typescript
// Tailwind CSS animation for slide-in from right
// Use translate-x-full -> translate-x-0 transition
// Auto-dismiss: useEffect with setTimeout per toast
// Max 3 visible, "+N more" collapse for overflow
```

### Data Directory Configuration
```python
# Store persistent data in a .wfs_data directory next to the shared folder
# e.g., if shared_folder is /Users/rahul/shared, data lives at /Users/rahul/.wfs_data/
# This avoids polluting the shared folder while keeping data nearby
from pathlib import Path

def get_data_dir(shared_folder: Path) -> Path:
    """Return the data directory for persistent storage.
    Creates the directory if it does not exist.
    """
    data_dir = shared_folder.parent / ".wfs_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Socket.IO library | Native WebSocket API | Stable since ES6 | No need for Socket.IO; native API handles all LAN use cases |
| Polling for updates | WebSocket push | Long-standing | Real-time without polling overhead |
| localStorage sync between tabs | WebSocket broadcast | N/A | Cross-device sync, not just cross-tab |
| react-use-websocket package | Custom useWebSocket hook | Ongoing | Avoids dependency for simple use case; full control over reconnect logic |

**Deprecated/outdated:**
- Socket.IO: Overkill for this project. Adds ~60KB client bundle, requires separate server package. Native WebSocket is sufficient for LAN single-server use.
- `starlette-websockets-demo`/`broadcaster`: Designed for multi-process scaling with Redis. This is a single-process LAN tool.

## Open Questions

1. **Data directory location**
   - What we know: Must be outside the shared folder to avoid polluting user files.
   - What's unclear: Should it be `shared_folder.parent / ".wfs_data"` or a system-level path like `~/.wfs_data`?
   - Recommendation: Use `shared_folder.parent / ".wfs_data"` -- keeps data collocated with the shared folder, easy to find, easy to clean up. Add to ServerConfig.

2. **Device name collision**
   - What we know: Random adjective+animal names will occasionally collide.
   - What's unclear: Does collision matter for a LAN tool with 2-10 devices?
   - Recommendation: Low risk. Append a short random number if collision detected. Not worth over-engineering.

3. **Max snippet count and character limits**
   - What we know: Need some limit to prevent abuse/memory issues.
   - Recommendation: 50 snippets max, 10,000 characters per snippet. Generous for a LAN tool. Enforce on server side.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml [tool.pytest.ini_options]` |
| Quick run command | `uv run pytest server/tests/ -x --timeout=10` |
| Full suite command | `uv run pytest server/tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RTME-01 | WebSocket connects and accepts | integration | `uv run pytest server/tests/test_websocket.py::TestWebSocketConnect -x` | No -- Wave 0 |
| RTME-01 | Device count broadcast on connect/disconnect | integration | `uv run pytest server/tests/test_websocket.py::TestDeviceTracking -x` | No -- Wave 0 |
| RTME-02 | Toast broadcast on file upload | integration | `uv run pytest server/tests/test_websocket.py::TestToastBroadcast -x` | No -- Wave 0 |
| RTME-03 | Clipboard snippet CRUD | unit | `uv run pytest server/tests/test_clipboard_service.py -x` | No -- Wave 0 |
| RTME-03 | Clipboard sync via WebSocket | integration | `uv run pytest server/tests/test_websocket.py::TestClipboardSync -x` | No -- Wave 0 |
| RTME-04 | File request create and list | unit | `uv run pytest server/tests/test_file_request_service.py -x` | No -- Wave 0 |
| RTME-04 | File request broadcast via WebSocket | integration | `uv run pytest server/tests/test_websocket.py::TestFileRequestBroadcast -x` | No -- Wave 0 |
| RTME-05 | File request fulfillment | unit+integration | `uv run pytest server/tests/test_file_request_service.py::TestFulfillment -x` | No -- Wave 0 |
| N/A | JSON persistence atomic read/write | unit | `uv run pytest server/tests/test_persistence.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/ -x --timeout=10`
- **Per wave merge:** `uv run pytest server/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_websocket.py` -- WebSocket connect, broadcast, device tracking, message routing (uses Starlette TestClient `websocket_connect`)
- [ ] `server/tests/test_clipboard_service.py` -- Clipboard snippet CRUD, persistence
- [ ] `server/tests/test_file_request_service.py` -- File request CRUD, fulfillment, persistence
- [ ] `server/tests/test_persistence.py` -- Atomic JSON read/write utility

Note: WebSocket tests use Starlette's `TestClient.websocket_connect()` which is synchronous (not async). This differs from the existing async test pattern with httpx. Both patterns can coexist in the same test suite.

## Sources

### Primary (HIGH confidence)
- FastAPI official docs: WebSocket advanced guide (https://fastapi.tiangolo.com/advanced/websockets/) -- ConnectionManager pattern, WebSocketDisconnect handling
- Starlette TestClient docs (https://www.starlette.io/testclient/) -- websocket_connect testing pattern
- Vite server options docs (https://vite.dev/config/server-options) -- ws:true proxy configuration
- Pydantic unions docs (https://docs.pydantic.dev/latest/concepts/unions/) -- discriminated union pattern for message types
- Direct inspection of installed packages: FastAPI 0.135.1, Starlette 0.52.1, websockets 16.0, aiofiles 25.1.0, Pydantic 2.12.5

### Secondary (MEDIUM confidence)
- Better Stack FastAPI WebSockets guide (https://betterstack.com/community/guides/scaling-python/fastapi-websockets/) -- broadcast error handling patterns
- DEV.to: Using WebSockets with React.js without library (https://dev.to/itays123/using-websockets-with-react-js-the-right-way-no-library-needed-15d0) -- custom hook architecture
- DEV.to: Exponential backoff reconnection strategies (https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1) -- backoff formula with jitter

### Tertiary (LOW confidence)
- None -- all claims verified against official docs or installed package versions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed, verified via `uv pip list`
- Architecture: HIGH -- ConnectionManager pattern is from official FastAPI docs, adapted for project conventions
- Pitfalls: HIGH -- well-documented issues from official sources and direct codebase analysis (e.g., SPA catch-all ordering)
- Testing: HIGH -- Starlette TestClient websocket_connect verified in official docs, existing pytest infrastructure confirmed

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- all dependencies are already locked in pyproject.toml and package.json)
