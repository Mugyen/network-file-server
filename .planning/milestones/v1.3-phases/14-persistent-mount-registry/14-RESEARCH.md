# Phase 14: Persistent Mount Registry - Research

**Researched:** 2026-03-30
**Domain:** aiosqlite-backed mount persistence for FastAPI relay
**Confidence:** HIGH

## Summary

Phase 14 replaces the in-memory `MountRegistry` with a SQLite-backed implementation using `aiosqlite`. The current registry stores mount metadata (code, status, agent IP, created_at, expires_at) in a Python dict that is lost on process restart. The new implementation persists this metadata in SQLite so mounts survive relay restarts, agents can reclaim OFFLINE mounts by IP match, and expired records are cleaned up automatically.

The most significant technical concern is the **time.monotonic() to time.time() migration**. The entire codebase currently uses monotonic timestamps for `created_at` and `expires_at` fields. Monotonic time resets on process restart, making it meaningless for persistence. All timestamp handling in the registry, agent_ws.py, and ttl_sweep.py must switch to wall-clock time (`time.time()`). This is a cross-cutting change that affects every caller.

**Primary recommendation:** Build a drop-in `SqliteMountRegistry` class with the same public API as `MountRegistry`, backed by aiosqlite with a single long-lived connection. Convert all timestamp usage from monotonic to wall-clock time. Change agent_ws.py disconnect handler from deregister to mark_offline, and add reclaim logic for OFFLINE mounts.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- SQLite at `/tmp/mounts.db` with `journal_mode=DELETE` -- survives relay process restarts but NOT Cloud Run redeploys (ephemeral /tmp)
- Accept mount code loss on redeploy -- this is a friends-tier relay, not mission-critical
- DB path configurable via `db_path` in config.yaml + `RELAY_DB_PATH` env var override (consistent with existing config module pattern)
- Use `aiosqlite` as the async SQLite library
- Log INFO message on startup when no existing DB is found ("No existing mount database -- starting fresh")
- Agent reconnecting with `?code=abc` reclaims an OFFLINE mount if: (a) the code exists and is OFFLINE, (b) the agent IP matches the original registration IP
- TTL continues from original registration -- if 6h of 24h have passed, agent gets 18h remaining (no reset)
- If the mount is already EXPIRED, reject the preferred code and assign a fresh random code
- Relay includes `"reclaimed": true` and `"remaining_ttl": N` in the `mount_registered` response so the agent CLI can display "Reclaimed mount abc123 (18h remaining)"
- Same-IP requirement prevents code hijacking -- only the original registrant can reclaim
- EXPIRED records are retained for 6 hours after expiry, then permanently deleted from SQLite
- OFFLINE mounts expire at their original `expires_at` -- no separate offline timeout (TTL sweep handles this)
- On cold start: clean up already-expired records and mark all remaining as OFFLINE before accepting connections
- Startup loads only valid, reclaimable mounts -- clean slate
- SQLite is the source of truth for all mount metadata (status, TTL, IP, timestamps)
- New SQLite-backed class replaces MountRegistry entirely -- same API (register, deregister, get_connection, etc.) but backed by SQLite for metadata
- Live TunnelConnection objects stored in an in-memory dict within the new class (connections can't be serialized to SQLite)
- Every proxy request queries SQLite for status check -- acceptable at 300 req/min scale with single-row lookups
- Follows existing singleton pattern: get_registry/set_registry -- same function names, new backing implementation
- App factory creates the new registry with DB path from config, installs via set_registry()

### Claude's Discretion
- SQLite schema design (column names, types, indexes)
- Exact startup loading sequence and error handling
- Whether to use a connection pool or single connection for aiosqlite
- How the retention window cleanup integrates with existing TTL sweep (same task or separate)
- Migration strategy for existing in-memory-only tests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERS-01 | Mount metadata (code, agent IP, status, created_at, expires_at) persists in SQLite across relay restarts | SqliteMountRegistry class with aiosqlite, schema design, startup loading sequence |
| PERS-02 | On relay restart, all previously-online mounts are marked offline until their agent reconnects | Cold-start cleanup logic in lifespan: DELETE expired, UPDATE remaining to OFFLINE |
| PERS-03 | Agents reconnecting with a preferred code reclaim their existing mount record | Reclaim logic in agent_ws.py: check status=OFFLINE + IP match, update status to ONLINE |
| PERS-04 | Expired mounts are cleaned up from SQLite by a background sweep | TTL sweep extension: delete records where expired_at + 6h retention < now |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.22.1 | Async SQLite interface | User-locked decision; wraps stdlib sqlite3 with asyncio, no event loop blocking |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlite3 (stdlib) | bundled | Underlying SQLite engine | Implicitly used by aiosqlite; provides PRAGMA, type adapters |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiosqlite | aiosqlitepool | Connection pool unnecessary at 300 req/min single-instance scale |
| aiosqlite | raw sqlite3 in thread | aiosqlite is exactly this, with cleaner API |

**Installation:**
```bash
uv add aiosqlite
```

## Architecture Patterns

### Recommended Module Structure
```
relay/app/services/
├── mount_registry.py    # Keep: generate_mount_code(), MountRecord dataclass,
│                        #   get_registry()/set_registry() singleton functions,
│                        #   abstract-ish interface
├── sqlite_registry.py   # NEW: SqliteMountRegistry class (same API, SQLite-backed)
└── ttl_sweep.py         # Modified: add expired record deletion after retention window
```

### Pattern 1: SqliteMountRegistry as Drop-In Replacement

**What:** A new class that implements the same public interface as `MountRegistry` but stores metadata in SQLite and connections in a companion in-memory dict.

**When to use:** This is the sole implementation going forward.

**Key design:**
```python
class SqliteMountRegistry:
    """SQLite-backed mount registry with in-memory connection tracking.

    SQLite stores: code, status, agent_ip, created_at, expires_at, ttl_warned
    In-memory dict stores: code -> TunnelConnection (cannot be serialized)
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db
        self._connections: dict[str, TunnelConnection] = {}

    async def register(self, code, connection, agent_ip, created_at, expires_at) -> None:
        # INSERT OR REPLACE into SQLite + store connection in memory

    async def deregister(self, code) -> None:
        # DELETE from SQLite + remove from memory dict

    async def get_connection(self, code) -> TunnelConnection:
        # Query SQLite for status, raise typed exceptions, return from memory

    async def mark_offline(self, code) -> None:
        # UPDATE status in SQLite + remove connection from memory

    async def reclaim(self, code, connection, agent_ip) -> ReclaimResult:
        # Check OFFLINE + IP match, UPDATE status to ONLINE, store connection
        # Returns remaining_ttl for the mount_registered response

    # ... other methods follow same pattern
```

### Pattern 2: Wall-Clock Timestamps (CRITICAL MIGRATION)

**What:** All `created_at` and `expires_at` fields switch from `time.monotonic()` to `time.time()`.

**Why mandatory:** `time.monotonic()` returns seconds since an arbitrary point (usually boot). After a process restart, the monotonic clock resets to a different epoch, making stored values meaningless. `time.time()` returns Unix epoch seconds, which are stable across restarts.

**Affected locations:**
- `relay/app/routers/agent_ws.py` line 123: `now: float = time.monotonic()` -> `time.time()`
- `relay/app/services/ttl_sweep.py` line 27: `now: float = time.monotonic()` -> `time.time()`
- `MountRecord` dataclass: `created_at` and `expires_at` semantics change
- All test files that pass `time.monotonic()` for `created_at`/`expires_at`

**Note:** `time.monotonic()` in `mount_proxy.py` is for request duration measurement only and stays unchanged.

### Pattern 3: Async Initialization via Factory Function

**What:** Since `aiosqlite.connect()` is async, the registry cannot be created in a synchronous constructor. Use an async factory.

**Example:**
```python
@classmethod
async def create(cls, db_path: str) -> "SqliteMountRegistry":
    """Create and initialize a SQLite-backed registry.

    Opens the database, creates the schema if needed, runs startup
    cleanup, and returns a ready-to-use registry.
    """
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=DELETE")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS mounts (
            code TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            agent_ip TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL,
            ttl_warned INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db.commit()
    registry = cls(db)
    await registry._startup_cleanup()
    return registry
```

### Pattern 4: Lifespan Integration

**What:** The app factory `create_relay_app()` is synchronous but the new registry requires async init. Move registry creation into the lifespan context manager.

**Example:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = get_config()
    registry = await SqliteMountRegistry.create(config.db_path)
    set_registry(registry)

    sweep_task = asyncio.create_task(
        run_ttl_sweep(registry, config)
    )
    yield
    sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass
    await registry.close()
```

**Note:** Currently `set_registry(MountRegistry())` is called at the end of `create_relay_app()`. This moves into the lifespan since SQLite init is async.

### Pattern 5: Agent Disconnect -> Mark Offline (Not Deregister)

**What:** Currently `agent_ws.py` line 157 calls `registry.deregister(assigned_code)` in the `finally` block. With persistence, disconnected mounts should be marked OFFLINE (not deleted) so the agent can reclaim on reconnect.

**Change:**
```python
# Before (current):
registry.deregister(assigned_code)

# After:
await registry.mark_offline(assigned_code)
```

### Anti-Patterns to Avoid
- **Opening a new aiosqlite connection per request:** Use a single long-lived connection initialized at startup and closed at shutdown. At 300 req/min, connection overhead would dominate.
- **Storing TunnelConnection references in SQLite:** Connections are live WebSocket objects; they cannot be serialized. Keep them in an in-memory dict keyed by mount code.
- **Using time.monotonic() with SQLite persistence:** Monotonic timestamps are meaningless after restart. Always use time.time() for persisted timestamps.
- **Synchronous SQLite calls on the event loop:** Always use aiosqlite's async methods; never call sqlite3 directly from async code.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SQLite access | Thread pool + sqlite3 wrapper | aiosqlite 0.22.1 | Already handles thread delegation, cursor proxying, error propagation |
| Connection pooling | Custom pool manager | Single aiosqlite connection | Single-instance relay at 300 req/min; one connection is sufficient |
| Schema migration | Custom version tracking | `CREATE TABLE IF NOT EXISTS` | Only one table, no migrations needed for v1 |

## Common Pitfalls

### Pitfall 1: Monotonic Time Across Restarts
**What goes wrong:** Stored `expires_at` values become nonsensical after restart because monotonic clock epoch changes.
**Why it happens:** `time.monotonic()` is explicitly defined as having an undefined epoch that can differ across runs.
**How to avoid:** Use `time.time()` for all persisted timestamps. Update agent_ws.py, ttl_sweep.py, and all tests.
**Warning signs:** Mounts immediately expiring or never expiring after restart.

### Pitfall 2: Sync Interface vs Async Registry
**What goes wrong:** Existing callers like `has_mount()` and `count_mounts_by_ip()` are called synchronously. Making the registry async changes every call site.
**Why it happens:** The current `MountRegistry` is purely in-memory with sync methods.
**How to avoid:** Make all registry methods `async`. Every call site already runs in async context (FastAPI route handlers, WebSocket handlers, async TTL sweep). Add `await` at each call site.
**Warning signs:** `RuntimeWarning: coroutine was never awaited`.

### Pitfall 3: Forgetting to Remove Connection on Mark Offline
**What goes wrong:** Memory leaks from stale TunnelConnection objects in the in-memory dict after agent disconnects.
**Why it happens:** `mark_offline()` updates SQLite status but forgets to clear the in-memory connection reference.
**How to avoid:** `mark_offline()` must both UPDATE SQLite status and `del self._connections[code]`.
**Warning signs:** Growing memory usage over time.

### Pitfall 4: Race Between Reclaim and Deregister
**What goes wrong:** Agent reconnects while the old disconnect handler is still running, causing the reclaim to succeed then immediately be undone by the old deregister.
**Why it happens:** WebSocket disconnect is async and the finally block may execute after the new connection's registration.
**How to avoid:** The disconnect handler should use `mark_offline()` not `deregister()`. If the mount is already ONLINE (reclaimed), `mark_offline()` should be a no-op or check status first.
**Warning signs:** Agent connects, receives mount_registered, then immediately loses the mount.

### Pitfall 5: Test Database File Cleanup
**What goes wrong:** Tests leave `.db` files on disk, causing cross-test pollution.
**Why it happens:** SQLite creates real files.
**How to avoid:** Use `:memory:` for unit tests or `tmp_path` fixture with cleanup. For integration tests that need file persistence, use pytest's `tmp_path`.
**Warning signs:** Flaky tests that pass individually but fail in suite.

### Pitfall 6: Forgetting `await db.commit()` After Writes
**What goes wrong:** INSERT/UPDATE/DELETE statements are buffered but never committed; data lost on connection close.
**Why it happens:** aiosqlite (like sqlite3) uses implicit transactions; writes require explicit commit.
**How to avoid:** Call `await self._db.commit()` after every write operation, or use `await self._db.execute(); await self._db.commit()` pattern consistently.
**Warning signs:** Data appears to save in tests but disappears after reconnecting to the DB.

## Code Examples

### Schema Design
```python
# Source: aiosqlite docs + SQLite PRAGMA docs
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mounts (
    code TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'online',
    agent_ip TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL,
    ttl_warned INTEGER NOT NULL DEFAULT 0
)
"""
# INDEX on agent_ip for count_mounts_by_ip queries
CREATE_IP_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mounts_agent_ip ON mounts (agent_ip)
"""
# INDEX on status for active_mounts queries and expired record cleanup
CREATE_STATUS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_mounts_status ON mounts (status)
"""
```

### Startup Cleanup Sequence
```python
async def _startup_cleanup(self) -> None:
    """Run cold-start cleanup: delete expired records, mark remaining as OFFLINE."""
    now = time.time()

    # Delete records that expired more than 6h ago (retention window)
    retention_cutoff = now - (6 * 3600)
    await self._db.execute(
        "DELETE FROM mounts WHERE status = ? AND expires_at IS NOT NULL AND expires_at < ?",
        (MountStatus.EXPIRED.value, retention_cutoff),
    )

    # Mark any still-expired records (within retention window) as EXPIRED
    await self._db.execute(
        "UPDATE mounts SET status = ? WHERE expires_at IS NOT NULL AND expires_at < ?",
        (MountStatus.EXPIRED.value, now),
    )

    # Mark all remaining non-expired mounts as OFFLINE
    await self._db.execute(
        "UPDATE mounts SET status = ? WHERE status = ?",
        (MountStatus.OFFLINE.value, MountStatus.ONLINE.value),
    )

    await self._db.commit()
```

### Reclaim Logic in agent_ws.py
```python
# In agent_websocket handler, replace current code assignment block:

# Current (line 116-119):
# if code is not None and not registry.has_mount(code):
#     assigned_code = code
# else:
#     assigned_code = generate_mount_code()

# New reclaim-aware logic:
reclaimed = False
remaining_ttl: int | None = None

if code is not None:
    reclaim_result = await registry.try_reclaim(code, conn, client_ip)
    if reclaim_result is not None:
        assigned_code = code
        reclaimed = True
        remaining_ttl = reclaim_result.remaining_ttl
    elif not await registry.has_mount(code):
        assigned_code = code
    else:
        assigned_code = generate_mount_code()
else:
    assigned_code = generate_mount_code()
```

### Reclaim Method on Registry
```python
@dataclass(frozen=True)
class ReclaimResult:
    """Result of a successful mount reclaim."""
    remaining_ttl: int

async def try_reclaim(
    self, code: str, connection: TunnelConnection, agent_ip: str
) -> ReclaimResult | None:
    """Attempt to reclaim an OFFLINE mount by code and IP match.

    Returns ReclaimResult with remaining_ttl on success, None on failure
    (code not found, not OFFLINE, IP mismatch, or expired).
    """
    async with self._db.execute(
        "SELECT status, agent_ip, expires_at FROM mounts WHERE code = ?",
        (code,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    status, stored_ip, expires_at = row

    if status != MountStatus.OFFLINE.value:
        return None
    if stored_ip != agent_ip:
        return None

    now = time.time()
    if expires_at is not None and expires_at <= now:
        return None  # Expired -- caller should assign fresh code

    # Reclaim: update status to ONLINE, store connection
    await self._db.execute(
        "UPDATE mounts SET status = ? WHERE code = ?",
        (MountStatus.ONLINE.value, code),
    )
    await self._db.commit()
    self._connections[code] = connection

    remaining = int(expires_at - now) if expires_at is not None else 0
    return ReclaimResult(remaining_ttl=remaining)
```

### Extended TTL Sweep for Retention Cleanup
```python
async def sweep_once(registry: SqliteMountRegistry, config: RelayConfig) -> None:
    """Sweep: expire online mounts past TTL, delete retained expired records."""
    now = time.time()
    mounts = await registry.active_mounts()

    # Existing: expire and warn online mounts
    for mount in mounts:
        # ... existing expiry/warning logic using wall-clock time ...

    # New: delete expired records past 6h retention window
    retention_cutoff = now - (6 * 3600)
    await registry.delete_expired_before(retention_cutoff)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-memory dict registry | SQLite-backed registry | Phase 14 | Mounts survive restarts |
| time.monotonic() timestamps | time.time() timestamps | Phase 14 | Required for persistence |
| Deregister on disconnect | Mark offline on disconnect | Phase 14 | Enables reconnect reclaim |

**Deprecated/outdated:**
- `MountRegistry` (in-memory): replaced by `SqliteMountRegistry`; remove class after migration, keep `MountRecord` dataclass, `generate_mount_code()`, and singleton functions

## Open Questions

1. **Should mark_offline guard against already-ONLINE mounts?**
   - What we know: A race condition exists where an agent reconnects before the old disconnect handler runs.
   - What's unclear: Whether the old handler's `mark_offline()` would undo the reclaim.
   - Recommendation: `mark_offline()` should only transition ONLINE -> OFFLINE. If status is already ONLINE with a different connection, skip the transition. Alternatively, disconnect handler should check if the connection it holds is still the registered one.

2. **Should the `MountRecord` dataclass be kept or replaced?**
   - What we know: Current tests and callers use `MountRecord` for in-memory representation.
   - What's unclear: Whether to return MountRecord from SQLite queries or use raw tuples.
   - Recommendation: Keep `MountRecord` for the return type of `active_mounts()`. Construct it from SQLite row data. The `connection` field becomes optional (None for OFFLINE mounts loaded from disk).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio (auto mode) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run python -m pytest tests/relay/ -x -q` |
| Full suite command | `uv run python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 | Mount metadata persists in SQLite | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py -x` | Wave 0 |
| PERS-02 | Cold start marks all mounts OFFLINE | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_startup_marks_online_as_offline -x` | Wave 0 |
| PERS-03 | Reconnecting agent reclaims OFFLINE mount | unit+integration | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_reclaim_offline_mount -x` | Wave 0 |
| PERS-04 | Expired mounts cleaned from SQLite by sweep | unit | `uv run python -m pytest tests/relay/test_sqlite_registry.py::test_delete_expired_retention -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run python -m pytest tests/relay/ -x -q`
- **Per wave merge:** `uv run python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/relay/test_sqlite_registry.py` -- covers PERS-01 through PERS-04 (schema init, CRUD, startup cleanup, reclaim, retention deletion)
- [ ] Update `tests/relay/conftest.py` -- fixtures need async registry creation with `:memory:` DB
- [ ] Update all existing tests that use `MountRegistry()` directly -- switch to async-compatible setup
- [ ] `aiosqlite` dependency: `uv add aiosqlite` -- not currently installed

## Sources

### Primary (HIGH confidence)
- [aiosqlite API docs](https://aiosqlite.omnilib.dev/en/latest/api.html) -- connection management, execute/commit patterns, context managers
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) -- v0.22.1, Python >=3.9, MIT license
- [SQLite PRAGMA docs](https://sqlite.org/pragma.html) -- journal_mode=DELETE is the default
- Codebase analysis: `relay/app/services/mount_registry.py`, `relay/app/routers/agent_ws.py`, `relay/app/services/ttl_sweep.py`, `relay/app/config.py`, `relay/app/main.py`

### Secondary (MEDIUM confidence)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) -- async context manager pattern for startup/shutdown
- Agent reconnect flow: `agent/connection.py` -- sends `?code=preferred_code` on reconnect, does NOT send ttl

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- aiosqlite is user-locked, version verified on PyPI
- Architecture: HIGH -- full codebase analysis of all integration points, clear migration path
- Pitfalls: HIGH -- identified through direct code reading (monotonic time, sync-to-async, race conditions)

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable domain, no fast-moving dependencies)
