# External Integrations

**Analysis Date:** 2026-03-09

## APIs & External Services

**None.** This is a self-contained local network file server with no external API calls.

The only outbound network operation is a UDP socket connection to `8.8.8.8:80` in `wifi_file_server.py` line 26, used solely to discover the machine's local IP address (no data is sent/received).

## Data Storage

**Databases:**
- None - No database used

**File Storage:**
- Local filesystem only
- Shared folder path set at runtime via CLI argument
- Stored in global variable `SHARED_FOLDER` in `wifi_file_server.py` line 20
- Files served via `flask.send_file()` (`wifi_file_server.py` line 98)
- Uploads saved via `werkzeug` file object `.save()` (`wifi_file_server.py` line 129)

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None - No authentication mechanism
- The server is open to any device on the local network
- Flask `secret_key` is hardcoded (`wifi_file_server.py` line 17) but only used for flash message sessions, not for actual auth

## Monitoring & Observability

**Error Tracking:**
- None - Errors are caught with bare `except` clauses and displayed as flash messages or printed to stdout

**Logs:**
- Flask's default request logging to stdout
- Custom print statements for server startup info (`wifi_file_server.py` lines 190-195)
- No structured logging framework

## CI/CD & Deployment

**Hosting:**
- Local machine only - Designed to run on a user's personal computer
- No containerization (no Dockerfile)
- No deployment configuration

**CI Pipeline:**
- None - No CI/CD configuration files present

## Environment Configuration

**Required env vars:**
- None - All configuration is via CLI arguments

**Secrets location:**
- Flask `secret_key` is hardcoded in source (`wifi_file_server.py` line 17)
- No `.env` file or secrets management

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## HTTP Endpoints (Internal API)

The Flask server exposes these routes (all in `wifi_file_server.py`):

| Method | Route | Handler | Purpose |
|--------|-------|---------|---------|
| GET | `/` | `index()` line 58 | Web UI - file listing page |
| GET | `/download/<filename>` | `download_file()` line 85 | File download |
| POST | `/upload` | `upload_file()` line 103 | File upload (multipart form) |
| GET | `/api/files` | `api_files()` line 137 | JSON API - file listing |

---

*Integration audit: 2026-03-09*
