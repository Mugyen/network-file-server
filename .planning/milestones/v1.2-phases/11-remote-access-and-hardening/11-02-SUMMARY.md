---
phase: 11-remote-access-and-hardening
plan: "02"
subsystem: client-spa
tags: [frontend, relay, remote-mount, vitest, react]
dependency_graph:
  requires: []
  provides: [remote-mount-url-helpers, remote-badge]
  affects: [client/src/api/client.ts, client/src/hooks/useWebSocket.ts, client/src/main.tsx, client/src/App.tsx]
tech_stack:
  added: [vitest, jsdom]
  patterns: [module-level-constant-computed-at-load, dynamic-import-for-test-isolation]
key_files:
  created:
    - client/src/utils/remoteMount.ts
    - client/src/utils/remoteMount.test.ts
    - client/vitest.config.ts
  modified:
    - client/src/api/client.ts
    - client/src/hooks/useWebSocket.ts
    - client/src/main.tsx
    - client/src/components/ModeBadges.tsx
    - client/src/App.tsx
decisions:
  - "MOUNT_PREFIX is a module-level constant computed once at load time via detectMountPrefix() — avoids per-call regex overhead and keeps all helpers pure"
  - "Tests use vi.resetModules() + dynamic import per describe block to force fresh module evaluation for each pathname stub"
  - "auth.ts requires no changes — it delegates to apiPost from client.ts which already uses the dynamic API_BASE"
metrics:
  duration: 2 minutes
  completed: "2026-03-11"
  tasks_completed: 2
  files_modified: 8
---

# Phase 11 Plan 02: SPA Remote Mount Adapter Summary

**One-liner:** React SPA detects /m/{code}/ relay prefix at load time and dynamically routes all API and WebSocket calls through the relay, with a green "Remote" badge in the header.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | remoteMount.ts utility with vitest setup and tests | e06c975 | remoteMount.ts, remoteMount.test.ts, vitest.config.ts, package.json |
| 2 | Wire remoteMount into all API call sites and add Remote badge | 18ae915 | client.ts, useWebSocket.ts, main.tsx, ModeBadges.tsx, App.tsx |

## What Was Built

### remoteMount.ts

Module-level constant `MOUNT_PREFIX` is computed once at load time by applying `/^(\/m\/[^/]+)/` regex to `window.location.pathname`. Four exports:

- `getApiBase()` — returns `/api` in LAN mode or `/m/{code}/api` in remote mode
- `getWsUrl(wsPath, queryString)` — builds fully-qualified ws:// or wss:// URL with mount prefix
- `isRemoteMount()` — boolean check for remote mode
- `getMountPrefix()` — raw prefix string for testing

### Wired call sites

All four API call sites now use dynamic URLs:
1. `client.ts` `API_BASE` — initialized from `getApiBase()`
2. `client.ts` `uploadWithProgress` — uses `API_BASE` (automatically updated)
3. `main.tsx` auth probe — uses `${getApiBase()}/files`
4. `useWebSocket.ts` WebSocket URL — uses `getWsUrl("/ws", ...)`

`auth.ts` delegates to `apiPost` from `client.ts` and needed no direct changes.

### Remote badge

`ModeBadges.tsx` gains a `remote: boolean` prop. When true, renders a green pill with Globe icon ("Remote") matching the existing Lock/Protected badge pattern.

### Vitest setup

Installed `vitest` and `jsdom`. `vitest.config.ts` sets jsdom environment. 11 tests pass covering LAN and remote modes for all exported functions, using `vi.resetModules()` + dynamic import for module-per-test isolation.

## Verification

```
vitest run:  11/11 tests passed
tsc --noEmit: 0 errors
vite build:  built in 2.48s (warnings are pre-existing, not errors)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

## Self-Check: PASSED

All files and commits verified present.
