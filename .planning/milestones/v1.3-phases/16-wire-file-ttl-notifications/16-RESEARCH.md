# Phase 16: Wire File TTL Notifications & Expired Files Handler - Research

**Researched:** 2026-04-03
**Domain:** WebSocket broadcast wiring, tunnel control message dispatch, test fixture alignment
**Confidence:** HIGH

## Summary

Phase 16 is a gap closure phase addressing 2 unsatisfied requirements (FTTL-04, FTTL-06), 2 broken integrations, and 2 broken E2E flows discovered during the v1.3 milestone audit. All three issues are wiring bugs -- the code that generates and handles messages exists but is either not connected (broadcast_fn=None) or silently dropped (run_receive_loop ignores unknown message types). A fourth item is a stale test assertion.

The fixes are surgical: (1) wire a broadcast function into `run_file_ttl_sweep` so toast messages reach browsers connected to the drop box, (2) keep drop box browser WebSocket connections alive instead of immediately closing them, (3) add handler branches in `TunnelConnection.run_receive_loop` for `delete_expired_files` and `keep_expired_files` control messages, and (4) update the config test to expect `/tmp/relay-data`.

**Primary recommendation:** Fix three wiring defects and one stale test, each isolated to 1-3 lines of change in well-understood modules. No new libraries or architectural changes needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FTTL-04 | Connected browsers receive a WebSocket toast notification when a file is auto-deleted | Wire broadcast_fn from drop box ConnectionManager into run_file_ttl_sweep; keep drop box browser WS connections alive via ASGIWebSocketTransport bridge |
| FTTL-06 | On mount restart, user is prompted whether to keep or delete files with expired TTLs | Add handler branches for delete_expired_files/keep_expired_files in tunnel/connection.py run_receive_loop, forwarding to file_ttl_db.delete_expired_for_mount |
</phase_requirements>

## Standard Stack

### Core (already in project -- no new dependencies)

| Library | Version | Purpose | Already Used |
|---------|---------|---------|--------------|
| FastAPI | >=0.115.0 | WebSocket endpoints, ASGI app | Yes |
| httpx-ws | >=0.8.2 | ASGIWebSocketTransport for bridging browser WS to drop box server app | Yes (agent/proxy.py) |
| aiosqlite | >=0.22.1 | File TTL database operations | Yes |

### No New Dependencies Required

This phase requires zero new libraries. All fixes use existing modules and patterns already established in the codebase.

## Architecture Patterns

### Pattern 1: Drop Box WebSocket Bridge (for FTTL-04)

**What:** The browser connects via WebSocket to `/m/dropbox/ws?device_name=...`. Currently, `proxy_websocket` in `mount_proxy.py:277-279` detects the drop box code and immediately closes the connection. The fix must bridge this WebSocket to the drop box server app's `/ws` endpoint.

**Why it broke:** The drop box uses `httpx.ASGITransport` for HTTP requests (which works fine), but WebSocket connections cannot be forwarded via httpx -- they need `httpx_ws.ASGIWebSocketTransport`. The Phase 15 implementation added the HTTP path but skipped the WS path.

**Current broken code (`mount_proxy.py:276-280`):**
```python
# Drop box WebSocket: accept and close gracefully (httpx can't forward WS)
if code == get_config().dropbox_code:
    await websocket.accept()
    await websocket.close(code=1000)
    return
```

**Fix pattern -- use ASGIWebSocketTransport like agent/proxy.py does:**

The agent already has an identical pattern in `handle_ws_open_frame` (agent/proxy.py:108-189) where it bridges tunnel WS frames to a local ASGI app via `httpx_ws.ASGIWebSocketTransport`. The relay needs the same approach for the drop box.

The fix replaces the accept-and-close with a bidirectional bridge:
1. Accept the browser WebSocket
2. Open a local WebSocket to the drop box server app using `ASGIWebSocketTransport`
3. Bridge messages bidirectionally between the browser WS and the local WS
4. Clean up when either side disconnects

**Key detail:** The drop box server app is created by `init_dropbox()` in `relay/app/services/dropbox.py`. Currently only the `httpx.AsyncClient` is stored. The fix must also store a reference to the raw ASGI app object so that `ASGIWebSocketTransport(app=app)` can be used in the WebSocket bridge. This means `init_dropbox()` must return both the client and the app, or the app must be stored separately.

### Pattern 2: Wiring broadcast_fn (for FTTL-04)

**What:** The `run_file_ttl_sweep` function accepts a `broadcast_fn` parameter but receives `None` at `main.py:74`. The fix wires the drop box server app's `ConnectionManager.broadcast_all` as the broadcast function.

**Current broken code (`main.py:73-74`):**
```python
file_ttl_sweep_task = asyncio.create_task(
    run_file_ttl_sweep(file_ttl_db, Path(config.data_dir), config.dropbox_code, 60, None)
)
```

**Fix:** Import and reference `server.app.services.connection_manager.manager` and pass `manager.broadcast_all` as the broadcast_fn. However, there's a subtlety: the `manager` singleton in the drop box server app is module-level, and the drop box server creates its own app instance. The `manager` is shared (it's a module-level singleton in `server/app/services/connection_manager.py`). Since `init_dropbox()` calls `create_app()` which includes the websocket router using this same `manager`, the module-level `manager` is the correct instance to use for broadcasting to browsers connected to the drop box.

The broadcast message format from `file_ttl_sweep.py:49-53` sends:
```python
{"type": "toast", "message": f"File expired and removed: {Path(fp).name}"}
```

The client-side `useToast` hook expects `WSToastPayload` format:
```typescript
{
  type: "toast",
  toast_type: ToastType,
  message: string,
  device_name: string,
  timestamp: string,
}
```

**Important:** The current broadcast message format in `file_ttl_sweep.py` is missing `toast_type`, `device_name`, and `timestamp` fields. The broadcast_fn needs to either: (a) have the sweep produce full toast payloads matching what the client expects, or (b) wrap the sweep's output in a full toast payload. The simplest approach is to have the sweep produce the correct payload format directly, adding a `toast_type` like "file_expired" (new ToastType), `device_name` as "System", and `timestamp` as current UTC ISO string.

**Client-side consideration:** The client's `ToastType` enum (`client/src/types/websocket.ts:18-24`) and server's `ToastType` enum (`server/app/models/enums.py:29-35`) do not include a `file_expired` type. However, the client's `useWebSocket` hook at line 66 checks `msgType === WSMessageType.TOAST` and routes to `addToast` handler regardless of `toast_type` value. So the existing client code will display any toast with `type: "toast"` -- the `toast_type` is used for visual styling but the message text is what matters. A new `toast_type` value like `"file_expired"` will work without client changes, as the toast displays the `message` field directly.

### Pattern 3: Tunnel Message Handler (for FTTL-06)

**What:** `TunnelConnection.run_receive_loop` at `tunnel/connection.py:276-293` only handles `pong` and `ping` text messages. The agent sends `delete_expired_files` and `keep_expired_files` control messages that fall through silently.

**Current code (`tunnel/connection.py:282-288`):**
```python
elif "text" in frame_dict:
    text = frame_dict["text"]
    message: dict = json.loads(text)
    if message.get("type") == "pong":
        self.handle_pong()
    elif message.get("type") == "ping":
        await self.send_control({"type": "pong"})
```

**Fix approach:** Add an extensible control message handler. Two options:

1. **Add specific branches** (minimal, matches existing pattern):
   ```python
   elif message.get("type") in ("delete_expired_files", "keep_expired_files"):
       if self._control_handler is not None:
           await self._control_handler(message)
   ```

2. **Add a generic callback** (more extensible):
   Add a `control_message_handler` callback to TunnelConnection that gets called for any unrecognized text message type.

Option 2 is better because TunnelConnection is a shared tunnel module -- it should not have knowledge of file TTL concepts. A generic callback keeps the tunnel module clean and application-specific logic in the relay's agent_ws.py.

**Wiring location:** In `agent_ws.py`, after creating the `TunnelConnection` but before calling `run_receive_loop`, register a handler:
```python
async def _handle_control(msg: dict) -> None:
    msg_type = msg.get("type")
    if msg_type in ("delete_expired_files", "keep_expired_files"):
        code = msg.get("code", assigned_code)
        try:
            file_ttl_db = get_file_ttl_db()
            await file_ttl_db.delete_expired_for_mount(code)
        except RuntimeError:
            pass  # FileTtlDb not initialized

conn.set_control_handler(_handle_control)
```

Both `delete_expired_files` and `keep_expired_files` result in the same DB operation: clearing expired records for the mount. In the delete case, the agent has already deleted the files locally before sending the message. In the keep case, the user chose to keep the files, so we clear the TTL records so they aren't re-prompted.

### Pattern 4: Config Test Fix

**What:** `test_load_config_data_dir_default` asserts `config.data_dir == "/data/"` but `config.yaml` was changed to `/tmp/relay-data`.

**Fix:** Change the test assertion from `"/data/"` to `"/tmp/relay-data"`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WS-to-ASGI bridge | Custom WebSocket forwarding | `httpx_ws.ASGIWebSocketTransport` | Already used in agent/proxy.py; handles ASGI protocol correctly |
| Toast broadcast | Custom WS connection tracking | `server.app.services.connection_manager.manager.broadcast_all` | Already manages connections, handles dead connection cleanup |
| Control message routing | Hardcoded if/elif chains in TunnelConnection | Generic callback registration | Keeps tunnel module application-agnostic |

## Common Pitfalls

### Pitfall 1: Drop Box App Reference
**What goes wrong:** `init_dropbox()` only returns an `httpx.AsyncClient` -- the raw ASGI app is needed for `ASGIWebSocketTransport` but isn't stored.
**Why it happens:** The original design only needed HTTP forwarding, not WebSocket.
**How to avoid:** Modify `init_dropbox()` to also store/return the server app, or store it alongside the client in a setter.
**Warning signs:** `ASGIWebSocketTransport(app=???)` has no app to reference.

### Pitfall 2: ConnectionManager Singleton Scope
**What goes wrong:** The `manager` singleton in `server/app/services/connection_manager.py` is module-level. If the drop box app and the WS bridge use different instances, broadcasts won't reach browsers.
**Why it happens:** Module-level singletons are shared across all imports of the module.
**How to avoid:** Verify that the drop box's `create_app()` and the WS bridge both use the same `manager` instance. Since it's module-level, this should work automatically as long as the same Python module is imported.
**Warning signs:** Broadcasts sent but not received by browsers; device count is 0 despite connected clients.

### Pitfall 3: Toast Payload Format Mismatch
**What goes wrong:** `file_ttl_sweep.py` produces `{"type": "toast", "message": "..."}` but the client expects `toast_type`, `device_name`, and `timestamp` fields.
**Why it happens:** The sweep was written to match a simpler broadcast contract that doesn't exist in the actual client.
**How to avoid:** Update the broadcast payload in `file_ttl_sweep.py` to include all required fields, or wrap the message in the broadcast_fn before sending.
**Warning signs:** Toast appears in browser but with undefined styling or missing information.

### Pitfall 4: Agent Receive Loop vs Relay Receive Loop
**What goes wrong:** The fix for FTTL-06 must modify `tunnel/connection.py`'s `run_receive_loop` (relay side), NOT `agent/connection.py`'s `_agent_receive_loop_with_metadata` (agent side). The agent side already handles `expired_files` correctly.
**Why it happens:** Both sides have receive loops but with different responsibilities.
**How to avoid:** The agent sends `delete_expired_files`/`keep_expired_files` messages, the relay's `TunnelConnection.run_receive_loop` receives them. The fix is on the relay side (tunnel/connection.py).
**Warning signs:** Testing on wrong receive loop; agent changes that break existing functionality.

### Pitfall 5: WS Bridge Cleanup
**What goes wrong:** Browser disconnects from the drop box WS but the local ASGI WS remains open, leaking resources.
**Why it happens:** Bidirectional bridge requires both tasks to be cancelled on either-side disconnect.
**How to avoid:** Use the same asyncio.wait(FIRST_COMPLETED) + cancel pattern already used in `mount_proxy.py:319-333` and `agent/proxy.py:166-179`.
**Warning signs:** Growing number of open connections in connection_manager; memory leaks under load.

## Code Examples

### Example 1: ASGIWebSocketTransport Bridge (from agent/proxy.py)
```python
# Source: agent/proxy.py:143-181 (verified in codebase)
async with ASGIWebSocketTransport(app=app) as ws_transport:
    async with httpx_ws.aconnect_ws(
        local_ws_url,
        httpx.AsyncClient(transport=ws_transport),
        headers=headers,
        keepalive_ping_interval_seconds=None,
    ) as local_ws:
        async def relay_to_local() -> None:
            async for chunk in conn.read_stream_iter(ws_id):
                await local_ws.send_text(chunk.decode("utf-8"))

        async def local_to_relay() -> None:
            while True:
                message = await local_ws.receive_text()
                await conn.send_ws_data(ws_id, message.encode("utf-8"))

        relay_task = asyncio.create_task(relay_to_local())
        local_task = asyncio.create_task(local_to_relay())
        # ... FIRST_COMPLETED wait + cancel pattern
```

### Example 2: ConnectionManager.broadcast_all (from server)
```python
# Source: server/app/services/connection_manager.py:76-88
async def broadcast_all(self, message: dict) -> None:
    dead: list[str] = []
    for dev_id, ws in list(self.active_connections.items()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(dev_id)
    for dev_id in dead:
        self.disconnect(dev_id)
```

### Example 3: Full Toast Payload (from server/app/routers/websocket.py)
```python
# Source: server/app/routers/websocket.py:19-27
def _make_toast(toast_type: ToastType, message: str, device_name: str) -> dict:
    return {
        "type": "toast",
        "toast_type": toast_type.value,
        "message": message,
        "device_name": device_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

### Example 4: TunnelConnection text frame handling (current)
```python
# Source: tunnel/connection.py:276-293
elif "text" in frame_dict:
    text = frame_dict["text"]
    message: dict = json.loads(text)
    if message.get("type") == "pong":
        self.handle_pong()
    elif message.get("type") == "ping":
        await self.send_control({"type": "pong"})
    # MISSING: no handler for delete_expired_files / keep_expired_files
```

## Detailed Fix Specifications

### Fix 1: Wire broadcast_fn + Keep Drop Box WS Alive (FTTL-04)

**Files to modify:**

1. **`relay/app/services/dropbox.py`** -- Store the drop box ASGI app alongside the httpx client:
   - Add `_dropbox_app` module-level variable and getter `get_dropbox_app()`
   - `init_dropbox()` stores the server app via a setter before returning the client

2. **`relay/app/routers/mount_proxy.py`** -- Replace accept-and-close with WS bridge:
   - Import `httpx_ws`, `ASGIWebSocketTransport`, `get_dropbox_app`
   - In `proxy_websocket`, when `code == config.dropbox_code`: bridge to local app via `ASGIWebSocketTransport`
   - Use bidirectional bridge pattern from agent/proxy.py

3. **`relay/app/main.py`** -- Wire broadcast_fn:
   - Import `manager` from `server.app.services.connection_manager`
   - Pass `manager.broadcast_all` as the `broadcast_fn` parameter to `run_file_ttl_sweep`

4. **`relay/app/services/file_ttl_sweep.py`** -- Fix toast payload format:
   - Update broadcast message to include `toast_type`, `device_name`, and `timestamp` fields
   - Use `"file_expired"` as toast_type, `"System"` as device_name, UTC ISO timestamp

### Fix 2: Add Tunnel Message Handlers (FTTL-06)

**Files to modify:**

1. **`tunnel/connection.py`** -- Add control message callback support:
   - Add `_control_handler` attribute (optional async callable)
   - Add `set_control_handler()` method
   - In `run_receive_loop`, after ping/pong handling, call `_control_handler` for unrecognized text message types

2. **`relay/app/routers/agent_ws.py`** -- Register the handler:
   - After creating `TunnelConnection` and before `run_receive_loop()`, register a handler for `delete_expired_files` and `keep_expired_files`
   - Handler calls `file_ttl_db.delete_expired_for_mount(code)` for both message types

### Fix 3: Config Test (Tech Debt)

**File to modify:**

1. **`tests/relay/test_config.py`** -- Update assertion:
   - Change `assert config.data_dir == "/data/"` to `assert config.data_dir == "/tmp/relay-data"`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `uv run python -m pytest tests/relay/test_file_ttl.py tests/relay/test_agent_expired_files.py tests/relay/test_config.py tests/tunnel/test_connection.py -x -q` |
| Full suite command | `uv run python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FTTL-04 | Sweep broadcasts toast when file deleted | unit | `uv run python -m pytest tests/relay/test_file_ttl.py::test_sweep_broadcasts_toast -x` | Yes (existing, passes with mock broadcast_fn) |
| FTTL-04 | Drop box WS stays alive (not immediately closed) | unit | `uv run python -m pytest tests/relay/test_dropbox_ws.py -x` | No -- Wave 0 |
| FTTL-06 | Tunnel receives delete_expired_files and calls handler | unit | `uv run python -m pytest tests/tunnel/test_connection.py::test_control_handler_dispatch -x` | No -- Wave 0 |
| FTTL-06 | Agent expired files response processed by relay | integration | `uv run python -m pytest tests/relay/test_agent_expired_files.py -x` | Yes (partial -- tests relay->agent direction, not agent->relay) |
| tech-debt | Config data_dir default matches YAML | unit | `uv run python -m pytest tests/relay/test_config.py::test_load_config_data_dir_default -x` | Yes (currently failing) |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/relay/test_file_ttl.py tests/relay/test_agent_expired_files.py tests/relay/test_config.py tests/tunnel/test_connection.py -x -q`
- **Per wave merge:** `uv run python -m pytest tests/ -x -q && uv run python -m pytest server/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/relay/test_dropbox_ws.py` -- covers FTTL-04 WS bridge behavior
- [ ] `tests/tunnel/test_connection.py::test_control_handler_*` -- covers FTTL-06 generic control handler dispatch
- [ ] `tests/relay/test_agent_expired_files.py` -- extend with agent->relay direction test (delete/keep response handling)

## Open Questions

1. **Toast payload format alignment**
   - What we know: The sweep produces `{"type": "toast", "message": "..."}` but the client expects `toast_type`, `device_name`, `timestamp` fields. The client hook will still display the toast since it routes by `type == "toast"`.
   - What's unclear: Whether the missing fields cause visual issues or JavaScript errors in the client.
   - Recommendation: Add all required fields to the sweep's broadcast payload for correctness. Add `"file_expired"` to client-side `ToastType` if strict type checking is needed, or leave it as a string since the client handles unknown types gracefully.

2. **ConnectionManager singleton across drop box WS bridge and sweep**
   - What we know: The `manager` in `server/app/services/connection_manager.py` is module-level. The drop box server app uses this same module.
   - What's unclear: Whether the ASGIWebSocketTransport bridge's WS connections register with the same `manager` instance that the sweep broadcasts to.
   - Recommendation: Verify this works in testing. Since both import paths resolve to the same module, the singleton should be shared. If not, the bridge code can import `manager` directly.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `relay/app/main.py:74` -- confirms broadcast_fn=None
- Codebase inspection: `mount_proxy.py:277-279` -- confirms WS immediately closed for drop box
- Codebase inspection: `tunnel/connection.py:276-293` -- confirms only ping/pong handled
- Codebase inspection: `agent/proxy.py:108-189` -- ASGIWebSocketTransport pattern for WS bridge
- Codebase inspection: `server/app/services/connection_manager.py` -- broadcast_all interface
- Codebase inspection: `relay/config.yaml:8` -- data_dir is `/tmp/relay-data`
- Codebase inspection: `tests/relay/test_config.py:91` -- test expects `/data/`
- v1.3 Milestone Audit: `.planning/v1.3-MILESTONE-AUDIT.md` -- gap analysis

### Secondary (MEDIUM confidence)
- httpx-ws library usage pattern from agent/proxy.py (known working in production)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all patterns already in codebase
- Architecture: HIGH -- three surgical fixes, each following existing patterns
- Pitfalls: HIGH -- pitfalls identified from direct code inspection of broken paths
- Test coverage: HIGH -- existing test infrastructure covers the domain, small gaps identified

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable -- internal wiring fixes, no external dependencies changing)
