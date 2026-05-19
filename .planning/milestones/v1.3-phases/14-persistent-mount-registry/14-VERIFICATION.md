---
phase: 14-persistent-mount-registry
verified: 2026-03-30T13:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 14: Persistent Mount Registry Verification Report

**Phase Goal:** Mount codes and their metadata survive relay restarts — agents reconnect and reclaim their existing codes, and expired mounts are cleaned up automatically.
**Verified:** 2026-03-30T13:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | SqliteMountRegistry stores mount metadata in SQLite and retrieves it correctly after close/reopen | VERIFIED | `test_persistence_across_reopen` — registers mount, closes DB, reopens, confirms metadata (code, agent_ip, created_at, expires_at, status=OFFLINE) survives via `active_mounts()` |
| 2  | Startup cleanup marks all ONLINE mounts as OFFLINE and deletes expired records past retention | VERIFIED | `test_startup_marks_online_as_offline`, `test_startup_deletes_expired_past_retention`, `test_startup_marks_newly_expired_as_expired` — three distinct tests confirm each leg of `_startup_cleanup()` |
| 3  | Expired records older than 6h retention window are deleted by `delete_expired_before()` | VERIFIED | `test_delete_expired_before_removes_old_records` — deletes records with expires_at older than cutoff, preserves newer; TTL sweep calls `await registry.delete_expired_before(now - 6 * 3600)` in `ttl_sweep.py` line 59 |
| 4  | All registry methods are async and raise typed exceptions (MountNotFoundError, MountOfflineError, MountExpiredError) | VERIFIED | Every method in `sqlite_registry.py` is `async def`; typed exceptions raised in `get_connection`, `deregister`, `mark_offline`, `expire`, `try_reclaim`; 12 tests verify exception paths |
| 5  | Relay starts with SqliteMountRegistry initialized in lifespan, not MountRegistry in app factory | VERIFIED | `relay/app/main.py` line 31: `registry = await SqliteMountRegistry.create(config.db_path)` in lifespan; no `MountRegistry()` in `relay/app/` |
| 6  | Agent disconnect marks mount OFFLINE instead of deregistering it | VERIFIED | `agent_ws.py` finally block line 179: `await registry.mark_offline(assigned_code)`; `test_agent_disconnect_marks_mount_offline` test confirms mount still exists as OFFLINE |
| 7  | Agent reconnecting with `?code=X` reclaims OFFLINE mount if IP matches, receives `reclaimed=true` and `remaining_ttl` in response | VERIFIED | `agent_ws.py` lines 123-133: reclaim-aware logic with `try_reclaim`; `test_agent_reclaims_offline_mount_same_ip` confirms `reclaimed=True` and same code assigned |
| 8  | Agent reconnecting with `?code=X` where mount is EXPIRED gets a fresh random code instead | VERIFIED | `try_reclaim()` returns None for EXPIRED mounts (line 287); `has_mount` returns True for EXPIRED so `generate_mount_code()` branch fires; `test_try_reclaim_expired_returns_none` confirms behavior |
| 9  | TTL sweep uses `time.time()` for all comparisons and deletes expired records past 6h retention | VERIFIED | `ttl_sweep.py` line 30: `now: float = time.time()`; line 59: `await registry.delete_expired_before(retention_cutoff)`; `test_sweep_deletes_old_expired_records` confirms retention cleanup |
| 10 | All existing relay tests pass after migration from sync MountRegistry to async SqliteMountRegistry | VERIFIED | 166 relay tests green: `uv run python -m pytest tests/relay/ -x -q` — 166 passed in 0.83s |

**Score:** 10/10 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `relay/app/services/sqlite_registry.py` | SqliteMountRegistry with full async API matching MountRegistry interface, exports SqliteMountRegistry and ReclaimResult | VERIFIED | 360 lines; all async methods present: register, deregister, get_connection, mark_offline, expire, has_mount, count_mounts_by_ip, mount_count, active_mounts, try_reclaim, delete_expired_before, close, _startup_cleanup |
| `relay/app/config.py` | db_path field on RelayConfig | VERIFIED | Line 29: `db_path: str`; line 95-98: loads from YAML with `RELAY_DB_PATH` env override; default `/tmp/mounts.db` |
| `relay/config.yaml` | db_path default value | VERIFIED | Line 7: `db_path: /tmp/mounts.db` |
| `tests/relay/test_sqlite_registry.py` | Unit tests covering PERS-01, PERS-02, PERS-04; min 100 lines | VERIFIED | 573 lines; 39 tests, all pass |
| `relay/app/main.py` | Lifespan creates SqliteMountRegistry via async factory, closes on shutdown | VERIFIED | Lines 28-43: lifespan creates registry, sets singleton, starts sweep, cancels sweep and closes registry on shutdown |
| `relay/app/routers/agent_ws.py` | Reclaim logic for OFFLINE mounts, mark_offline on disconnect, time.time timestamps | VERIFIED | Lines 117-133: reclaim-aware code assignment; line 138: `now: float = time.time()`; line 179: `await registry.mark_offline(assigned_code)` |
| `relay/app/services/ttl_sweep.py` | Wall-clock timestamps, expire() for TTL expiry, retention cleanup | VERIFIED | Line 30: `time.time()`; line 43: `await registry.expire(mount.code)`; line 59: `await registry.delete_expired_before(retention_cutoff)` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `relay/app/main.py` | `relay/app/services/sqlite_registry.py` | `SqliteMountRegistry.create()` in lifespan | WIRED | Line 31: `registry = await SqliteMountRegistry.create(config.db_path)` |
| `relay/app/routers/agent_ws.py` | `relay/app/services/sqlite_registry.py` | `registry.try_reclaim()` and `await registry.mark_offline()` | WIRED | Lines 123, 179: both calls present and awaited |
| `relay/app/services/ttl_sweep.py` | `relay/app/services/sqlite_registry.py` | `registry.expire()` and `registry.delete_expired_before()` | WIRED | Lines 43 and 59: both calls present and awaited |
| `relay/app/routers/agent_ws.py` | `time` | `time.time()` replacing `time.monotonic()` for persistent timestamps | WIRED | Line 138: `now: float = time.time()`; no `time.monotonic` in `relay/app/` except `mount_proxy.py` (request duration, not registry timestamps — expected) |
| `relay/app/services/sqlite_registry.py` | `aiosqlite` | `aiosqlite.connect()` in `create()` factory | WIRED | Line 83: `db = await aiosqlite.connect(db_path)`; `pyproject.toml`: `aiosqlite>=0.22.1` |
| `relay/app/services/sqlite_registry.py` | `relay/app/services/mount_registry.py` | imports MountRecord | WIRED | Line 18: `from relay.app.services.mount_registry import MountRecord` |
| `relay/app/routers/mount_proxy.py` | async `get_connection()` | `await get_registry().get_connection(code)` | WIRED | Lines 94 and 225: both call sites properly awaited |
| `relay/app/routers/health.py` | `mount_count()` | `await registry.mount_count()` | WIRED | Line 18: `count: int = await registry.mount_count()` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PERS-01 | 14-01, 14-02 | Mount metadata (code, agent IP, status, created_at, expires_at) persists in SQLite across relay restarts | SATISFIED | `test_persistence_across_reopen` — data survives close/reopen cycle including status transition to OFFLINE |
| PERS-02 | 14-01, 14-02 | On relay restart, all previously-online mounts are marked offline until their agent reconnects | SATISFIED | `_startup_cleanup()` step 3: `UPDATE mounts SET status='offline' WHERE status='online'`; `test_startup_marks_online_as_offline` |
| PERS-03 | 14-02 | Agents reconnecting with a preferred code reclaim their existing mount record | SATISFIED | `try_reclaim()` in `sqlite_registry.py`; reclaim-aware block in `agent_ws.py` lines 122-133; `test_agent_reclaims_offline_mount_same_ip` |
| PERS-04 | 14-01, 14-02 | Expired mounts are cleaned up from SQLite by a background sweep | SATISFIED | `delete_expired_before()` called in `ttl_sweep.py` line 59 after each sweep; `test_sweep_deletes_old_expired_records` |

All 4 requirements covered. No orphaned requirements found.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `relay/app/routers/mount_proxy.py` (lines 85, 142, 174, 194) | `time.monotonic()` | INFO | These measure HTTP request duration for logging — not registry timestamps. Correct use of monotonic clock. Not a violation. |
| `tests/relay/test_mount_registry.py` | `MountRegistry()` and `time.monotonic()` | INFO | Tests for the legacy in-memory `MountRegistry` class (kept for backward compat per plan 14-02 decision). Class is no longer used in production code. Tests remain valid for the legacy class. Not a production concern. |

No blocker or warning-level anti-patterns found.

---

## Human Verification Required

None. All phase 14 goals are verifiable programmatically.

The following behaviors were confirmed via tests rather than manual inspection:
- Reclaim behavior end-to-end via WebSocket (`test_agent_reclaims_offline_mount_same_ip`)
- IP mismatch gets fresh code (test for `try_reclaim_ip_mismatch_returns_none`)
- Disconnect marks OFFLINE not deregistered (`test_agent_disconnect_marks_mount_offline`)
- Retention cleanup removes records past 6h window (`test_sweep_deletes_old_expired_records`)

---

## Summary

Phase 14 fully achieves its goal. All four PERS requirements are implemented and verified:

- **PERS-01 (Persistence):** `SqliteMountRegistry` stores all mount metadata in SQLite. The `test_persistence_across_reopen` test explicitly closes the DB and reopens it, confirming metadata survives.
- **PERS-02 (Startup cleanup):** `_startup_cleanup()` runs on every `create()` call — deletes stale expired records, marks newly-expired as EXPIRED, marks all ONLINE as OFFLINE. Three dedicated tests confirm each step.
- **PERS-03 (Reclaim):** `try_reclaim()` checks OFFLINE status + IP match + TTL validity, transitions to ONLINE, and returns `ReclaimResult`. `agent_ws.py` calls it before any fresh registration. `mount_registered` response includes `reclaimed=true` and `remaining_ttl`.
- **PERS-04 (Retention cleanup):** `delete_expired_before(cutoff)` is called in every TTL sweep iteration with a 6h lookback. Records transition ONLINE→EXPIRED (retained) via `expire()`, then are permanently deleted after the retention window.

The singleton pattern is correctly updated — `relay/app/main.py` lifespan is the sole owner of registry lifecycle. All relay callers properly `await` the async registry methods. 166 relay tests pass.

---

_Verified: 2026-03-30T13:00:00Z_
_Verifier: Claude (gsd-verifier)_
