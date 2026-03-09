# Bandwidth Throttling & QoS

## Summary
Control how much network bandwidth the file server uses. Set global limits, per-user limits, and per-transfer limits. Prioritize certain transfers over others. Prevent the server from saturating the network.

## Why This Matters
A large file transfer can make the entire WiFi network unusable for everyone. In shared environments (homes, offices, cafes), bandwidth control is essential courtesy. It also prevents abuse in public-facing scenarios (drop box mode, tunnel mode).

## Implementation
- Global bandwidth limit (e.g., max 50 Mbps total)
- Per-user bandwidth limit
- Per-transfer speed limit
- Priority levels: high, normal, low (queue-based)
- Fair-share mode: automatically divide bandwidth equally among active transfers
- Time-based rules: unlimited speed during off-hours, throttled during work hours
- Real-time bandwidth usage graph
- Burst allowance: allow full speed for first N MB, then throttle
- Admin controls: adjust limits per connected device

## Scope
Medium — 5-7 hours. Token bucket algorithm for rate limiting.

## Monetization
Team tier. Essential for shared/managed environments.
