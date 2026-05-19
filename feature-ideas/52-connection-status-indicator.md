# Connection Status Indicator in Web UI

## Summary
A visible connection status badge in the browser UI showing whether the host (agent) is online, offline, or if the mount has expired. Includes auto-retry with user feedback when the agent disconnects.

## Why This Matters
When a remote mount's agent goes offline (laptop sleeps, network drops, process killed), browser users get opaque errors or broken pages. A clear status indicator prevents confusion and sets expectations about when the share will come back.

## Implementation
- Status badge in the UI header: "Connected" (green), "Reconnecting..." (yellow), "Host Offline" (red), "Mount Expired" (gray)
- Detect agent status via WebSocket `/api/events` connection health (already exists)
- On WebSocket disconnect: show "Reconnecting..." with auto-retry countdown
- On relay returning 502/503 (agent offline): show "Host Offline — waiting for host to reconnect" overlay
- On relay returning 410 (mount expired): show "This share has expired" with no retry
- Graceful degradation page (full-page overlay) when agent is unreachable, replacing broken partial UI

## Scope
Small — 2-3 hours. React component + WebSocket health detection + relay error code handling.

## Monetization
Free tier. Core UX improvement.
