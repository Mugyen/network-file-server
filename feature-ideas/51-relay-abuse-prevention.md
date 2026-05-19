# Relay Abuse Prevention & Rate Limiting

## Summary
Protect the public relay from abuse with rate limiting, mount limits, mandatory TTLs, bandwidth caps, and CORS lockdown. Prevents the relay from being used as an open proxy or file hosting service.

## Why This Matters
A public relay without limits is an open proxy. Anyone can register unlimited mounts, transfer unlimited data, and use the relay for file hosting indefinitely. Rate limiting and abuse prevention are non-negotiable before any public deployment.

## Implementation

### Rate Limiting
- Per-IP rate limiting on mount registration (e.g., 5 mounts per hour per IP) using `slowapi` or in-memory token bucket
- Per-IP rate limiting on proxy requests (e.g., 100 req/min per IP)
- Per-mount bandwidth tracking with configurable caps (e.g., 1 GB/hour per mount)

### Mount Limits
- Max concurrent mounts per agent IP (e.g., 3)
- Max total active mounts on the relay (e.g., 100)
- Mandatory TTL on public relay — no indefinite mounts (max 24h, default 2h)

### CORS Lockdown
- Replace `allow_origins=["*"]` with relay's own origin on the relay server
- Keep wildcard CORS on the LAN server (safe due to network isolation)

### Request Validation
- Max request body size on proxy (e.g., 500 MB default, configurable)
- Reject oversized `Content-Length` headers at the relay before tunneling

## Scope
Medium — 4-6 hours. Rate limiting middleware + mount caps + CORS config + size validation.

## Monetization
Infrastructure. Required for sustainable public hosting.
