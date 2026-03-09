# Offline Mode & Local Caching

## Summary
Cache frequently accessed files locally in the browser so they remain available even when the server goes down or the device disconnects from WiFi. Sync changes when reconnected.

## Why This Matters
WiFi is unreliable. Devices move in and out of range. The server might restart. Offline mode means users can still browse and access recently viewed files without connectivity. This is the resilience that makes a tool feel enterprise-grade.

## Implementation
- Service Worker with Cache API for file caching
- "Make Available Offline" button per file
- Auto-cache recently accessed files (configurable cache size)
- Offline file browser showing cached files with "offline" badge
- Queue uploads made while offline, sync when reconnected
- Conflict resolution for files modified while offline
- Cache management UI: see cached files, total size, clear cache
- IndexedDB for metadata and clipboard items
- Background sync API for automatic reconnection

## Scope
Medium — 5-8 hours. Service Worker + Cache API.

## Monetization
Pro tier. Enterprise users need reliability guarantees.
