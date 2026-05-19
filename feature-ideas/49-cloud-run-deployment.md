# Cloud Run Deployment (Dockerized Relay)

## Summary
Dockerfile and Cloud Run configuration for hosting the relay server on Google Cloud. Includes health check endpoint, structured JSON logging, and managed TLS via Cloud Run's `*.run.app` domain.

## Why This Matters
The relay server uses long-lived WebSocket connections between agent and relay. Google Cloud Functions has hard request timeouts and poor WebSocket support. Cloud Run supports WebSockets natively (up to 60-min idle timeout), is containerized, has a generous free tier, and provides HTTPS with managed certs out of the box.

## Implementation
- `Dockerfile` for the relay: Python 3.11 slim base, `uv sync`, pre-built React SPA bundled in
- `GET /health` endpoint returning `{"status": "ok"}` for Cloud Run liveness probes and uptime monitoring
- Replace print-based logging with Python `logging` module outputting structured JSON (Cloud Run parses this automatically into its logging console)
- `Secure` flag on all session cookies when behind HTTPS (detect via `X-Forwarded-Proto` header)
- Cloud Run service config: `--min-instances=1` (to keep WebSocket connections alive), `--timeout=3600`, `--session-affinity`
- `.dockerignore` to exclude tests, planning docs, feature-ideas, node_modules source

## Scope
Medium — 4-6 hours. Dockerfile + health endpoint + logging + cookie secure flag + deploy config.

## Monetization
Infrastructure. Required for any hosted/public deployment.
