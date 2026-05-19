# Persistent Mount Registry

## Summary
Replace the in-memory `MountRegistry` with a persistent backend (Redis or SQLite) so mount state survives relay restarts, deploys, and Cloud Run instance recycling.

## Why This Matters
The relay's `MountRegistry` is entirely in-memory. When Cloud Run restarts the container (deploys, scaling events, crashes), all mount registrations are lost. Agents will reconnect, but any in-flight browser sessions break, and mount codes may change. A persistent registry ensures continuity.

## Implementation

### Option A: Redis (Recommended for Cloud Run)
- Google Cloud Memorystore (Redis) or Upstash Redis (serverless, free tier)
- Store mount metadata: code, agent IP, status (ONLINE/OFFLINE/EXPIRED), created_at, ttl, password_hash
- TunnelConnection objects remain in-memory (they hold live WebSocket state) — registry only tracks metadata
- On agent reconnect: look up existing code in Redis, re-associate with new TunnelConnection
- TTL enforcement via Redis key expiry

### Option B: Single-Instance with Graceful Shutdown
- Keep in-memory registry but run Cloud Run with `--min-instances=1`
- Handle SIGTERM gracefully: notify connected agents to reconnect
- Simpler but less resilient — instance replacement still causes brief outage

### Recommended Approach
Start with Option B (simpler, sufficient for friends-only use), migrate to Option A before public launch.

## Scope
Option B: Small — 1-2 hours. Option A: Medium — 4-6 hours.

## Monetization
Infrastructure. Required for reliable hosted deployment.
