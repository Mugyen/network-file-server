# Phase 15: UX Polish and Drop Box - Research

**Researched:** 2026-04-02
**Domain:** Relay landing page, connection status overlays, in-process drop box mount, per-file upload TTL with auto-deletion
**Confidence:** HIGH

## Summary

Phase 15 adds four user-facing feature groups to the relay: (1) a polished landing page with OG meta tags and static asset serving, (2) connection status overlays in the React SPA replacing the current redirect-on-error behavior, (3) an always-on in-process drop box mount backed by the server package's `create_app()`, and (4) per-file upload TTLs with SQLite tracking, background sweep, WebSocket toast notifications, and countdown badges.

The existing codebase provides strong foundations for all four areas. The Jinja2 template system (`base.html` + child templates) supports the landing page. The `handleRelayError()` function in `client/src/api/client.ts` is the exact location to replace redirect behavior with status-based state management. The `SqliteMountRegistry` supports registering the drop box as a first-class mount record, and the `ttl_sweep.py` pattern provides the template for file TTL background sweeps. The server's `create_app()` already produces a standalone FastAPI application that can be forwarded to via `httpx.ASGITransport`.

**Primary recommendation:** Implement in four sequential plans matching the four feature groups. The drop box (plan 3) is the most architecturally complex, requiring careful integration of the server app within mount_proxy via httpx.ASGITransport request forwarding and reserved code protection in the SQLite registry.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Landing page: Hero section layout with how-it-works strip, Jinja2 extending base.html, OG meta tags on all relay pages, OG image as static PNG asset (not SVG)
- Connection status: Banner + disabled UI pattern for both offline (503) and expired (410), REST polling via `GET /m/{code}/status` every 30s, auto-recovery on reconnect
- Drop box: In-process FastAPI mount importing server's `create_app()`, mount_proxy intercepts reserved code and routes to local app, full server API supported, registered as first-class SQLite mount record with null TTL
- File TTL: Dropdown in upload dialog (1h/6h/1d/7d/Never), per-batch TTL, SQLite `file_ttl` table, background sweep, WebSocket toast on deletion, countdown badges, auto-delete expired drop box files on boot
- Deployment: VPS with persistent disk, configurable `data_dir` via config.yaml + env var

### Claude's Discretion
- Exact landing page copy and styling beyond the layout decision
- Status endpoint response format details
- Banner component styling (colors, animation, exact wording)
- File TTL sweep interval
- How the server package is mounted within mount_proxy (ASGI sub-application vs request forwarding)
- docker-compose.yml structure and volume configuration
- SVG/PNG OG image design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LAND-01 | Landing page with description and mount code form | Jinja2 template extending base.html with hero section, how-it-works strip, code form |
| LAND-02 | Mount code form redirects to /m/{code}/ | Existing redirect logic in `landing.py` already works; enhance template form |
| LAND-03 | All pages include OG meta tags | Add `og:title`, `og:description`, `og:image` blocks in base.html head section |
| LAND-04 | Landing page links to GitHub repo | Simple anchor tag in hero section template |
| CONN-01 | "Host Offline" overlay on 503 | Replace `handleRelayError()` redirect with `useMountStatus` hook + REST polling |
| CONN-02 | "Mount Expired" overlay on 410 | Same status polling mechanism, terminal state (no auto-recovery) |
| CONN-03 | Overlays replace broken partial UI with full-page message | Banner at top + `pointer-events-none` / `opacity-50` on file list container |
| DROP-01 | Always-on mount in receive mode on boot | Register drop box in lifespan, create server app with `create_app()`, intercept in mount_proxy |
| DROP-02 | Drop box code configurable via env var | Add `dropbox_code` to RelayConfig with `RELAY_DROPBOX_CODE` env var override |
| DROP-03 | Reserved mount codes cannot be claimed by external agents | Guard in `agent_ws.py` rejecting registration/reclaim of reserved codes |
| DROP-04 | Landing page links to drop box | Template variable for drop box code, link in landing page |
| FTTL-01 | User selects TTL per file at upload | Add `ttl` query param to upload endpoint, dropdown in SPA upload flow |
| FTTL-02 | Default file TTL is 1 day | Server-side default when no TTL specified on upload |
| FTTL-03 | Expired files auto-deleted by background sweep | New `file_ttl_sweep.py` modeled on existing `ttl_sweep.py` pattern |
| FTTL-04 | WebSocket toast when file auto-deleted | Broadcast via `connection_manager.broadcast()` in sweep callback |
| FTTL-05 | File listing shows expiry badge | New `ExpiryBadge` React component, file listing API returns `expires_at` field |
| FTTL-06 | On mount restart, user prompted to keep/delete expired files | Agent CLI prompts on reconnect; drop box auto-deletes on boot |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | Web framework | Already the relay and server framework |
| Jinja2 | >=3.1.0 | HTML templates | Already used for landing page and error pages |
| aiosqlite | >=0.22.1 | Async SQLite | Already used for mount registry |
| React 18 | 18.x | SPA framework | Already the client framework |
| TailwindCSS | 3.x | Utility CSS | Already used for all SPA styling |
| httpx | >=0.28.0 | Async HTTP client | Already a dependency; ASGITransport for drop box forwarding |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI StaticFiles | (built-in) | Serve OG image and static assets | Mount at `/static/` in relay app |
| lucide-react | (existing) | Icons | Existing icon library for badges and banners |

### No New Dependencies Required

All features can be built with the existing dependency set. The key library for the drop box is `httpx` (already installed) with its `ASGITransport` for in-process request forwarding from mount_proxy to the server app.

## Architecture Patterns

### Recommended Changes to Project Structure
```
relay/
  static/
    og-image.png               # OG image (1200x630 PNG, checked into repo)
  templates/
    base.html                   # Add <meta> OG tag blocks, static mount URL
    landing.html                # Rewrite with hero section, how-it-works, drop box link
  app/
    config.py                   # Add data_dir, dropbox_code fields
    main.py                     # Mount StaticFiles, initialize drop box in lifespan
    routers/
      landing.py                # Pass dropbox_code to template context
      mount_proxy.py            # Intercept reserved code, forward to local server app
      agent_ws.py               # Reject reserved code registration
      status.py                 # NEW: GET /m/{code}/status endpoint
    services/
      dropbox.py                # NEW: Create and manage the drop box server app instance
      file_ttl_sweep.py         # NEW: Background file TTL sweep
      file_ttl_db.py            # NEW: SQLite file_ttl table operations

client/src/
  hooks/
    useMountStatus.ts           # NEW: REST polling hook for /m/{code}/status
  components/
    MountStatusOverlay.tsx      # NEW: Banner + disabled overlay for offline/expired
    ExpiryBadge.tsx             # NEW: Countdown badge for file TTL
  types/
    websocket.ts                # Add FILE_EXPIRED toast type
    files.ts                    # Add expires_at optional field to FileEntry
```

### Pattern 1: Drop Box via httpx.ASGITransport In-Process Forwarding

**What:** The relay creates a server `FastAPI` app via `create_app()` at startup, then uses `httpx.AsyncClient(transport=ASGITransport(app=server_app))` to forward requests from `mount_proxy.proxy_request()` when the code matches the reserved drop box code.

**When to use:** When the reserved drop box code is detected in `proxy_request()`.

**Why not `app.mount()`:** FastAPI's `app.mount("/path", subapp)` requires a static path prefix. The drop box lives under `/m/{dropbox_code}/` which is a dynamic path handled by `mount_proxy`'s catch-all route `"/m/{code}/{path:path}"`. Mounting at a fixed path would conflict with the existing route structure.

**Example:**
```python
# relay/app/services/dropbox.py
from pathlib import Path
from httpx import ASGITransport, AsyncClient
from server.app.config import ServerConfig, set_server_config
from server.app.main import create_app

_dropbox_client: AsyncClient | None = None

async def init_dropbox(data_dir: Path, dropbox_code: str) -> AsyncClient:
    """Create the drop box server app and return an httpx client for it."""
    dropbox_dir = data_dir / "dropbox"
    dropbox_dir.mkdir(parents=True, exist_ok=True)

    config = ServerConfig(
        shared_folder=dropbox_dir,
        port=0,  # Not used for in-process
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code=dropbox_code,
        relay_url=None,
    )
    set_server_config(config)
    server_app = create_app()
    transport = ASGITransport(app=server_app)
    client = AsyncClient(transport=transport, base_url="http://dropbox")
    return client
```

```python
# In mount_proxy.py proxy_request():
from relay.app.services.dropbox import get_dropbox_client

dropbox_client = get_dropbox_client()
if dropbox_client is not None and code == get_config().dropbox_code:
    # Forward to local server app instead of tunnel
    resp = await dropbox_client.request(
        method=request.method,
        url=f"/{path}",
        headers=dict(request.headers),
        content=await request.body(),
        params=str(request.url.query),
    )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )
```

**Confidence:** HIGH -- httpx.ASGITransport is already used in the test suite (`tests/relay/conftest.py`) and is a proven pattern in this codebase.

### Pattern 2: Connection Status REST Polling with `useMountStatus` Hook

**What:** A custom React hook that polls `GET /m/{code}/status` every 30 seconds, returning the current mount status (`"online"` | `"offline"` | `"expired"`). Replaces the current `handleRelayError()` redirect pattern with status-driven UI state.

**When to use:** In the main App component, only when in remote mount mode (`isRemoteMount()`).

**Example:**
```typescript
// client/src/hooks/useMountStatus.ts
import { useCallback, useEffect, useRef, useState } from "react";
import { getMountPrefix, isRemoteMount } from "../utils/remoteMount.ts";

export enum MountStatus {
  ONLINE = "online",
  OFFLINE = "offline",
  EXPIRED = "expired",
  UNKNOWN = "unknown",
}

const POLL_INTERVAL_MS = 30000;

export function useMountStatus(): MountStatus {
  const [status, setStatus] = useState<MountStatus>(MountStatus.UNKNOWN);
  const intervalRef = useRef<number | null>(null);

  const poll = useCallback(async (): Promise<void> => {
    if (!isRemoteMount()) {
      setStatus(MountStatus.ONLINE);
      return;
    }
    try {
      const resp = await fetch(`${getMountPrefix()}/status`);
      if (resp.ok) {
        const data = await resp.json() as { status: string };
        setStatus(data.status as MountStatus);
      } else {
        setStatus(MountStatus.UNKNOWN);
      }
    } catch {
      setStatus(MountStatus.UNKNOWN);
    }
  }, []);

  useEffect(() => {
    void poll();
    intervalRef.current = window.setInterval(() => void poll(), POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, [poll]);

  return status;
}
```

### Pattern 3: SQLite File TTL Table + Background Sweep

**What:** A new SQLite table `file_ttl` stores per-file expiry metadata. A background asyncio task (modeled on the existing `ttl_sweep.py`) deletes expired files and broadcasts WebSocket notifications.

**When to use:** Files uploaded with a TTL get a record in `file_ttl`. The sweep runs periodically.

**Example schema:**
```sql
CREATE TABLE IF NOT EXISTS file_ttl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mount_code TEXT NOT NULL,
    file_path TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE(mount_code, file_path)
);
CREATE INDEX IF NOT EXISTS idx_file_ttl_expires ON file_ttl (expires_at);
```

**Important design note:** For the drop box (in-process mount), the relay owns the SQLite database and the filesystem. The sweep can delete files directly. For agent-backed mounts, the relay does NOT have filesystem access -- it can only mark files as expired in the DB and notify the agent via a control message. The file TTL feature as specified primarily targets the drop box and in-process mounts.

### Pattern 4: OG Meta Tags via Jinja2 Template Blocks

**What:** Add meta tag blocks to `base.html` that child templates can override, providing default OG tags while allowing per-page customization.

**Example:**
```html
<!-- In base.html <head> -->
{% block og_tags %}
<meta property="og:title" content="{% block og_title %}Network File Server{% endblock %}" />
<meta property="og:description" content="{% block og_description %}Share files instantly — scan QR, drop files, done.{% endblock %}" />
<meta property="og:image" content="{{ url_for('static', path='og-image.png') }}" />
<meta property="og:type" content="website" />
{% endblock %}
```

### Anti-Patterns to Avoid

- **Mounting drop box as ASGI sub-app via `app.mount()`:** This conflicts with the dynamic `"/m/{code}/{path:path}"` catch-all route in mount_proxy. Use request forwarding instead.
- **Using SVG for OG image:** Social platforms (Facebook, Twitter/X, LinkedIn) do NOT support SVG in `og:image`. Use PNG at 1200x630 pixels, under 300KB.
- **Creating a separate WebSocket channel for status:** Decided against in STATE.md. Use REST polling at 30s intervals.
- **Redirecting on 503/410 in the SPA:** The current `handleRelayError()` redirects to the relay's Jinja2 error page, breaking the SPA experience. Replace with status-driven overlay state.
- **Polling when page is hidden:** Pause the status polling interval when `document.hidden === true` to avoid unnecessary network requests.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-process HTTP forwarding | Raw ASGI scope/receive/send manipulation | `httpx.ASGITransport` + `AsyncClient` | httpx handles all ASGI protocol details, already tested in this codebase |
| Static file serving | Manual file reading in route handlers | `FastAPI.StaticFiles(directory="relay/static")` | Handles content-type, caching headers, 404s correctly |
| OG image generation | Runtime SVG-to-PNG conversion | Pre-generated 1200x630 PNG checked into repo | Social platforms need real PNG; no runtime dependency needed |
| Countdown formatting | Custom time math for "2h left" badges | `Date` arithmetic with simple helper function | Small utility, but don't inline the logic in components |
| Background sweep scheduling | Custom timer management | Follow existing `run_ttl_sweep()` pattern: `while True: await asyncio.sleep(interval); await sweep_once()` | Proven pattern in this codebase |

**Key insight:** The httpx.ASGITransport approach is already battle-tested in this codebase's test infrastructure (`tests/relay/conftest.py` uses it for all relay integration tests). Reusing it for the drop box forwarding is a natural extension.

## Common Pitfalls

### Pitfall 1: Drop Box Server Config Collision
**What goes wrong:** The server package uses a module-level `_config` singleton (`server.app.config`). If the relay calls `set_server_config()` for the drop box, it may collide with any existing server config in the same process.
**Why it happens:** The relay and server share the same Python process when the drop box is enabled.
**How to avoid:** The drop box is the ONLY server instance in the relay process, so the singleton is fine. But call `set_server_config()` before `create_app()` and ensure it happens exactly once during relay lifespan initialization. Do NOT re-call it.
**Warning signs:** `RuntimeError: Server config has not been set` or unexpected shared folder path.

### Pitfall 2: Mount Proxy HTML Rewriting for Drop Box
**What goes wrong:** The existing `rewrite_html_asset_paths()` in mount_proxy rewrites `src="/assets/..."` to `src="/m/{code}/assets/..."`. When forwarding to the local server app via httpx, the HTML response will contain `/assets/...` paths that need the same rewriting.
**Why it happens:** The server app generates HTML with root-relative paths, same as a remote agent.
**How to avoid:** Apply the same HTML path rewriting to drop box responses. Since the request flows through `proxy_request()`, the existing rewriting code already applies if the response is HTML. Ensure the drop box forwarding path goes through the same rewriting logic.
**Warning signs:** Broken CSS/JS in the drop box SPA -- 404s for `/assets/...` instead of `/m/dropbox/assets/...`.

### Pitfall 3: Reserved Code Race Condition
**What goes wrong:** An external agent sends a WebSocket registration request with the reserved drop box code before the relay's lifespan completes drop box initialization.
**Why it happens:** `agent_ws.py` processes connections as they arrive; if the reserved code check is only in `register()`, timing matters.
**How to avoid:** Add the reserved code check at the TOP of `agent_websocket()` in `agent_ws.py`, before any rate limit or reclaim logic. Check against config, not the registry.
**Warning signs:** Drop box code claimed by an external agent, drop box stops working.

### Pitfall 4: File TTL for Agent-Backed Mounts
**What goes wrong:** The relay records file TTL in SQLite but cannot delete files on a remote agent's filesystem.
**Why it happens:** The relay is a proxy; it has no filesystem access to agent-backed mounts.
**How to avoid:** For Phase 15, file TTL auto-deletion works only for the in-process drop box mount. For agent-backed mounts, the relay can track TTL metadata and notify via WebSocket toast, but actual file deletion requires agent cooperation (FTTL-06 handles this with a prompt on reconnect). Document this boundary clearly.
**Warning signs:** Files marked expired in SQLite but still present on the agent.

### Pitfall 5: Status Endpoint Path Conflict
**What goes wrong:** Adding `GET /m/{code}/status` may conflict with the existing catch-all `"/m/{code}/{path:path}"` route in mount_proxy.
**Why it happens:** FastAPI routes are matched in order of inclusion; the catch-all may intercept `/status` before a dedicated status route.
**How to avoid:** Add the status endpoint in `mount_proxy.py` BEFORE the catch-all route, or handle it as a special case inside `proxy_request()` by checking if `path == "status"`. Given that mount_proxy already handles the catch-all, handling it inside `proxy_request()` is simpler and avoids route ordering issues.
**Warning signs:** `/m/{code}/status` returns a proxied response from the agent instead of the relay's status JSON.

### Pitfall 6: OG Image URL Must Be Absolute
**What goes wrong:** Social media crawlers require an absolute URL for `og:image` (not a relative path).
**Why it happens:** The Jinja2 template renders `url_for('static', path='og-image.png')` which produces a relative path like `/static/og-image.png`.
**How to avoid:** Build the absolute URL using `request.url_for('static', path='og-image.png')` or construct it from `request.base_url`. Pass this as a template variable.
**Warning signs:** Social previews show no image despite the meta tag being present.

## Code Examples

### Status Endpoint (inside proxy_request or separate handler)
```python
# Option: Handle status check inside proxy_request before tunnel forwarding
@router.get("/m/{code}/status")
async def mount_status(code: str) -> dict[str, str]:
    """Return the current status of a mount code.

    Returns JSON: {"status": "online"|"offline"|"expired"|"not_found"}
    """
    registry = get_registry()
    try:
        await registry.get_connection(code)
        return {"status": "online"}
    except MountOfflineError:
        return {"status": "offline"}
    except MountExpiredError:
        return {"status": "expired"}
    except MountNotFoundError:
        return {"status": "not_found"}
```

**Important:** This route MUST be included in the router BEFORE the catch-all `"/m/{code}/{path:path}"` route, or FastAPI will match the catch-all first. Alternatively, check for `path == "status"` inside `proxy_request()`.

### Reserved Code Guard in agent_ws.py
```python
# At the top of agent_websocket(), after config retrieval:
config = get_config()
if code is not None and code == config.dropbox_code:
    await websocket.accept()
    await websocket.send_json({
        "type": "error",
        "error": "Reserved mount code",
    })
    await websocket.close(code=1008)
    return
```

### Drop Box Registration in Lifespan
```python
# In relay/app/main.py lifespan():
from relay.app.services.dropbox import init_dropbox, set_dropbox_client

config = get_config()
if config.dropbox_code:
    data_dir = Path(config.data_dir)
    dropbox_client = await init_dropbox(data_dir, config.dropbox_code)
    set_dropbox_client(dropbox_client)

    # Register drop box as a first-class mount in SQLite
    # Use a sentinel connection object or None-compatible approach
    await registry.register(
        code=config.dropbox_code,
        connection=None,  # No tunnel connection -- requests forwarded locally
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,  # Never expires
    )
```

**Note:** `register()` currently requires a non-None `TunnelConnection`. The drop box will need either: (a) the registry to accept `None` for the connection field for local mounts, or (b) a sentinel/mock connection object. Option (a) is cleaner -- update `SqliteMountRegistry.register()` to accept `TunnelConnection | None`.

### File TTL Upload Flow
```python
# In server/app/routers/files.py upload_files():
@router.post("/api/files/upload")
async def upload_files(
    files: list[UploadFile],
    path: str = Query(""),
    conflict_resolution: ConflictResolution | None = Query(None),
    ttl: int | None = Query(None),  # TTL in seconds, None means "Never"
    x_device_id: str | None = Header(None),
    x_device_name: str | None = Header(None),
) -> Any:
    # ... existing upload logic ...
    # After successful upload, if ttl is set, record in file_ttl table
```

### Expiry Badge Component
```typescript
// client/src/components/ExpiryBadge.tsx
interface ExpiryBadgeProps {
  expiresAt: string; // ISO timestamp
}

function formatTimeLeft(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (diff <= 0) return "Expired";
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(hours / 24);
  if (days > 0) return `${String(days)}d left`;
  if (hours > 0) return `${String(hours)}h left`;
  const minutes = Math.floor(diff / 60000);
  return `${String(minutes)}m left`;
}

function getUrgencyClass(expiresAt: string): string {
  const diff = new Date(expiresAt).getTime() - Date.now();
  const hours = diff / 3600000;
  if (hours < 1) return "text-red-600 dark:text-red-400";
  if (hours < 6) return "text-orange-600 dark:text-orange-400";
  return "text-gray-500 dark:text-gray-400";
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `handleRelayError()` redirects to Jinja2 error page | Status polling + SPA overlay | Phase 15 | SPA stays loaded, no page reload on transient errors |
| No static assets in relay | `StaticFiles(directory="relay/static")` mounted at `/static/` | Phase 15 | Enables OG image serving and future static assets |
| No OG meta tags | `og:title`, `og:description`, `og:image` on all pages | Phase 15 | Social link previews work |
| No drop box | In-process server app with httpx forwarding | Phase 15 | "Try without installing" experience |
| No file TTL | Per-file TTL with auto-deletion | Phase 15 | Files auto-clean from drop box |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` (testpaths = ["server/tests", "tests"]) |
| Quick run command | `uv run pytest tests/relay/ -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LAND-01 | Landing page has hero section and code form | unit | `uv run pytest tests/relay/test_landing.py -x` | Exists (extend) |
| LAND-02 | Code form redirects to /m/{code}/ | unit | `uv run pytest tests/relay/test_landing.py::test_code_redirect_returns_302 -x` | Exists |
| LAND-03 | OG meta tags on all pages | unit | `uv run pytest tests/relay/test_landing.py -x -k og` | Wave 0 |
| LAND-04 | Landing page links to GitHub | unit | `uv run pytest tests/relay/test_landing.py -x -k github` | Wave 0 |
| CONN-01 | Host Offline overlay on 503 | unit | `uv run pytest tests/relay/test_status.py -x` | Wave 0 |
| CONN-02 | Mount Expired overlay on 410 | unit | `uv run pytest tests/relay/test_status.py -x` | Wave 0 |
| CONN-03 | Overlays replace partial UI | manual-only | N/A (visual check in browser) | N/A |
| DROP-01 | Always-on mount on boot | integration | `uv run pytest tests/relay/test_dropbox.py -x` | Wave 0 |
| DROP-02 | Configurable code via env var | unit | `uv run pytest tests/relay/test_config.py -x -k dropbox` | Wave 0 |
| DROP-03 | Reserved codes cannot be claimed | unit | `uv run pytest tests/relay/test_dropbox.py -x -k reserved` | Wave 0 |
| DROP-04 | Landing page links to drop box | unit | `uv run pytest tests/relay/test_landing.py -x -k dropbox` | Wave 0 |
| FTTL-01 | TTL selection at upload | unit | `uv run pytest server/tests/test_upload.py -x -k ttl` | Wave 0 |
| FTTL-02 | Default TTL is 1 day | unit | `uv run pytest server/tests/test_upload.py -x -k default_ttl` | Wave 0 |
| FTTL-03 | Expired files auto-deleted | unit | `uv run pytest tests/relay/test_file_ttl.py -x` | Wave 0 |
| FTTL-04 | WebSocket toast on deletion | integration | `uv run pytest tests/relay/test_file_ttl.py -x -k toast` | Wave 0 |
| FTTL-05 | Expiry badge in listing | manual-only | N/A (visual check in browser) | N/A |
| FTTL-06 | Prompt on mount restart | integration | `uv run pytest tests/relay/test_file_ttl.py -x -k restart` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/relay/ server/tests/ -x -q`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/relay/test_status.py` -- covers CONN-01, CONN-02 (status endpoint tests)
- [ ] `tests/relay/test_dropbox.py` -- covers DROP-01, DROP-03 (drop box init, reserved code)
- [ ] `tests/relay/test_file_ttl.py` -- covers FTTL-03, FTTL-04, FTTL-06 (file TTL sweep, toast, restart)
- [ ] Extend `tests/relay/test_landing.py` -- covers LAND-03, LAND-04 (OG tags, GitHub link, drop box link)
- [ ] Extend `tests/relay/test_config.py` -- covers DROP-02 (dropbox_code config field)
- [ ] Extend `server/tests/test_upload.py` -- covers FTTL-01, FTTL-02 (TTL param on upload)

## Open Questions

1. **WebSocket forwarding for drop box**
   - What we know: The drop box server app has WebSocket endpoints (`/ws`). The relay's `proxy_websocket()` currently tunnels WebSocket through `TunnelConnection`. The drop box has no `TunnelConnection`.
   - What's unclear: Whether httpx.ASGITransport supports WebSocket forwarding (it does not -- httpx is HTTP-only).
   - Recommendation: For the drop box, the WebSocket at `/m/{dropbox_code}/ws` needs special handling. Options: (a) use `httpx-ws` (already a dependency) for WebSocket forwarding, (b) directly bridge the browser WebSocket to the server app's WebSocket handler using `wsproto` or raw ASGI, (c) mount the server's WebSocket handler directly. Option (c) is simplest: check if the request is a WebSocket upgrade for the reserved code, and handle it separately. This should be resolved during plan 3 implementation.

2. **`SqliteMountRegistry.register()` accepting None connection**
   - What we know: The current signature requires `TunnelConnection`. The drop box has no tunnel.
   - What's unclear: How much registry refactoring is needed.
   - Recommendation: Allow `connection: TunnelConnection | None` in `register()`. The `get_connection()` method should return a sentinel or raise for the drop box code since requests are forwarded differently. Alternatively, bypass `get_connection()` entirely for the reserved code in mount_proxy.

3. **File TTL for agent-backed mounts scope**
   - What we know: FTTL requirements mention "per file at upload" which could mean any mount.
   - What's unclear: Whether the relay can enforce file deletion on remote agents.
   - Recommendation: Phase 15 implements file TTL for the drop box only (relay has filesystem access). For agent-backed mounts, store TTL metadata and display badges, but defer auto-deletion to a future enhancement where agents cooperate via control messages. FTTL-06 handles the agent prompt on reconnect.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `relay/app/main.py`, `relay/app/routers/mount_proxy.py`, `relay/app/services/sqlite_registry.py`, `relay/app/services/ttl_sweep.py`, `relay/app/config.py`, `client/src/api/client.ts`, `client/src/hooks/useWebSocket.ts`
- [FastAPI Sub-Applications docs](https://fastapi.tiangolo.com/advanced/sub-applications/) -- confirmed `app.mount()` is static-path only
- [FastAPI Templates docs](https://fastapi.tiangolo.com/advanced/templates/) -- Jinja2 template patterns
- [HTTPX ASGITransport docs](https://www.python-httpx.org/advanced/transports/) -- in-process ASGI forwarding

### Secondary (MEDIUM confidence)
- [OpenGraph best practices](https://opengraph.gallery/blog/open-graph-images-guide.html) -- OG image format/size requirements (1200x630 PNG)
- [OG protocol spec](https://ogp.me/) -- required meta properties
- [React polling patterns](https://overreacted.io/making-setinterval-declarative-with-react-hooks/) -- Dan Abramov's useInterval pattern

### Tertiary (LOW confidence)
- None -- all findings verified against codebase and official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in the project, no new dependencies
- Architecture: HIGH -- patterns directly extend existing codebase patterns (ttl_sweep, mount_proxy, httpx.ASGITransport in tests)
- Pitfalls: HIGH -- identified through actual codebase inspection (route ordering, config singletons, HTML rewriting)
- Drop box WebSocket forwarding: MEDIUM -- open question on exact mechanism

**Research date:** 2026-04-02
**Valid until:** 2026-05-02 (stable -- all patterns are well-established)
