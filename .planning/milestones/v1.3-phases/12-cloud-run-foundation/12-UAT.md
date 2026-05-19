---
status: complete
phase: 12-cloud-run-foundation
source: [12-01-SUMMARY.md, 12-02-SUMMARY.md]
started: 2026-03-17T00:00:00Z
updated: 2026-03-17T00:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running relay. Start fresh with `uv run network-relay`. Server boots without errors and `curl localhost:8001/health` returns 200 with JSON containing `"status": "ok"` and a `"mounts"` field.
result: pass

### 2. Docker Build
expected: Running `docker build -t relay-test .` completes successfully with no errors. The multi-stage build (node:20-slim, python:3.11-slim, slim runtime) produces a working image.
result: pass

### 3. Docker Container Health Check
expected: Running `docker run --rm -e PORT=8080 -p 8080:8080 relay-test` starts the relay inside the container. `curl localhost:8080/health` returns 200 with JSON `{"status": "ok", "mounts": 0}`.
result: pass

### 4. Production JSON Logging
expected: Running `RELAY_ENV=production uv run network-relay` starts the relay. Log output to stdout is one JSON object per line with a `"severity"` field (e.g., `{"severity": "INFO", "message": "..."}`). No plain-text log lines mixed in.
result: pass

### 5. Dev Text Logging
expected: Running `uv run network-relay` (no RELAY_ENV set) starts the relay. Log output is human-readable text format (e.g., `INFO     relay.app: ...`), not JSON.
result: pass

### 6. CORS Production Lockdown
expected: Running `RELAY_ENV=production RELAY_ALLOWED_ORIGINS=https://example.com uv run network-relay`, then sending a CORS preflight from an unlisted origin is rejected. Repeating with the listed origin returns Access-Control-Allow-Origin with that origin.
result: pass

### 7. Deploy Script
expected: `cat deploy_relay.sh` shows a script that includes `gcloud builds submit`, `gcloud run deploy network-relay`, `--region us-central1`, `--max-instances 1`, `--allow-unauthenticated`, and `RELAY_ENV=production` in the env vars.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
