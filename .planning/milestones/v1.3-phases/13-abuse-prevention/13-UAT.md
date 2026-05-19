---
status: testing
phase: 13-abuse-prevention
source: [13-01-SUMMARY.md, 13-02-SUMMARY.md]
started: 2026-03-18T00:00:00Z
updated: 2026-03-18T00:00:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Cold Start Smoke Test
expected: |
  Kill any running relay. Start from scratch with `uv run python -m relay.cli --port 8080 ~/some-folder`. Relay boots without errors. `curl http://localhost:8080/health` returns 200 with a JSON body containing a mount count field.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running relay. Start from scratch with `uv run python -m relay.cli --port 8080 ~/some-folder`. Relay boots without errors. `curl http://localhost:8080/health` returns 200 with a JSON body containing a mount count field.
result: [pending]

### 2. Config Module Loads Defaults
expected: Start the relay without setting any RELAY_* env vars. The relay starts in development mode with default config values. Check the startup logs — no config errors. The relay serves requests normally on the configured port.
result: [pending]

### 3. Config Env Var Override
expected: Start the relay with `RELAY_RATE_PROXY_REQUEST=10/minute uv run python -m relay.cli --port 8080 ~/some-folder`. The proxy rate limit should now be 10/min instead of the default 300/min. Rapidly hitting a mounted path should trigger 429 much faster than normal.
result: [pending]

### 4. Proxy Rate Limiting Returns 429
expected: Connect an agent to the relay, then rapidly send many requests to `/m/{code}/` (e.g., a quick loop of `curl` requests). After exceeding the configured rate (300/min default or the override you set), the relay returns HTTP 429 with a `Retry-After` header in the response.
result: [pending]

### 5. 429 Styled Error Page in Browser
expected: Trigger a proxy rate limit in a browser (refresh a mounted page rapidly). Instead of a raw error, you see a styled error page with a retry countdown showing how many seconds to wait. The page matches the visual style of other relay error pages (not found, offline, expired).
result: [pending]

### 6. Mount TTL Cap Enforcement
expected: Connect an agent with a very large TTL (e.g., `?ttl=999999`). The relay should accept the connection but cap the TTL to the configured maximum (default 86400 seconds / 24 hours). The `mount_registered` control message should reflect the capped TTL, not the requested value.
result: [pending]

### 7. Per-IP Mount Cap
expected: From the same machine, start 5 agents connecting to the relay. All 5 connect successfully. Attempt to start a 6th agent from the same IP — the relay rejects it with a structured error message indicating the per-IP mount cap has been reached. The WebSocket closes with code 1008.
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0

## Gaps

[none yet]
