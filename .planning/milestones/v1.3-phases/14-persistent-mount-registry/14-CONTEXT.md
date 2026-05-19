# Phase 14: Persistent Mount Registry - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Mount codes and their metadata survive relay restarts. Agents reconnect and reclaim their existing codes. Expired mounts are cleaned up automatically. No new UI features, no landing page changes, no new agent CLI features.

</domain>

<decisions>
## Implementation Decisions

### Storage durability
- SQLite at `/tmp/mounts.db` with `journal_mode=DELETE` — survives relay process restarts but NOT Cloud Run redeploys (ephemeral /tmp)
- Accept mount code loss on redeploy — this is a friends-tier relay, not mission-critical
- DB path configurable via `db_path` in config.yaml + `RELAY_DB_PATH` env var override (consistent with existing config module pattern)
- Use `aiosqlite` as the async SQLite library
- Log INFO message on startup when no existing DB is found ("No existing mount database — starting fresh")

### Reconnect semantics
- Agent reconnecting with `?code=abc` reclaims an OFFLINE mount if: (a) the code exists and is OFFLINE, (b) the agent IP matches the original registration IP
- TTL continues from original registration — if 6h of 24h have passed, agent gets 18h remaining (no reset)
- If the mount is already EXPIRED, reject the preferred code and assign a fresh random code
- Relay includes `"reclaimed": true` and `"remaining_ttl": N` in the `mount_registered` response so the agent CLI can display "Reclaimed mount abc123 (18h remaining)"
- Same-IP requirement prevents code hijacking — only the original registrant can reclaim

### Record lifecycle
- EXPIRED records are retained for 6 hours after expiry, then permanently deleted from SQLite
- OFFLINE mounts expire at their original `expires_at` — no separate offline timeout (TTL sweep handles this)
- On cold start: clean up already-expired records and mark all remaining as OFFLINE before accepting connections
- Startup loads only valid, reclaimable mounts — clean slate

### Registry interface
- SQLite is the source of truth for all mount metadata (status, TTL, IP, timestamps)
- New SQLite-backed class replaces MountRegistry entirely — same API (register, deregister, get_connection, etc.) but backed by SQLite for metadata
- Live TunnelConnection objects stored in an in-memory dict within the new class (connections can't be serialized to SQLite)
- Every proxy request queries SQLite for status check — acceptable at 300 req/min scale with single-row lookups
- Follows existing singleton pattern: get_registry/set_registry — same function names, new backing implementation
- App factory creates the new registry with DB path from config, installs via set_registry()

### Claude's Discretion
- SQLite schema design (column names, types, indexes)
- Exact startup loading sequence and error handling
- Whether to use a connection pool or single connection for aiosqlite
- How the retention window cleanup integrates with existing TTL sweep (same task or separate)
- Migration strategy for existing in-memory-only tests

</decisions>

<specifics>
## Specific Ideas

- The replacement class should be a drop-in for MountRegistry — all existing callers (agent_ws.py, mount_proxy.py, ttl_sweep.py, health.py) should work with minimal changes
- agent_ws.py line 116 (`if code is not None and not registry.has_mount(code)`) needs to change — with persistence, OFFLINE mounts DO exist, so reclaim logic must check status + IP match

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `relay/app/services/mount_registry.py`: MountRegistry class with full API (register, deregister, get_connection, mark_offline, has_mount, count_mounts_by_ip, active_mounts) — new class replaces this with same interface
- `relay/app/services/ttl_sweep.py`: sweep_once/run_ttl_sweep — needs to also handle expired record deletion after retention window
- `relay/app/config.py`: RelayConfig dataclass + load_config with env var overrides — add db_path field here
- `relay/app/enums.py`: MountStatus enum (ONLINE, OFFLINE, EXPIRED) — already has all needed states

### Established Patterns
- Module-level singleton via get_registry/set_registry — new implementation follows same pattern
- App factory in create_relay_app() — initializes registry, starts TTL sweep via lifespan
- RelayConfig loaded from YAML + env vars — db_path follows same pattern
- FastAPI lifespan for background tasks — TTL sweep already runs here

### Integration Points
- `create_relay_app()` — initialize new SQLite-backed registry with db_path from config
- `agent_ws.py` line 116 — update reclaim logic for OFFLINE mounts (check status + IP match)
- `agent_ws.py` mount_registered message — add reclaimed/remaining_ttl fields
- `ttl_sweep.py` — extend to delete expired records after 6h retention window
- `lifespan()` — ensure DB is initialized and startup cleanup runs before accepting connections
- All test files using MountRegistry — update to use new implementation (may need async setup)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-persistent-mount-registry*
*Context gathered: 2026-03-30*
