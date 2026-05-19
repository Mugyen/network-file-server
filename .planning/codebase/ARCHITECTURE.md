# Architecture

**Analysis Date:** 2026-03-09

## Pattern Overview

**Overall:** Monolithic Flask application with server-rendered templates (Jinja2)

**Key Characteristics:**
- Single-module Python application with all route handlers and logic in one file
- Server-side rendered HTML via Flask/Jinja2 templates
- No database; filesystem is the sole data store
- Global mutable state for shared folder path configuration
- CLI-driven startup with argparse for configuration

## Layers

**Presentation Layer (Web UI):**
- Purpose: Renders the file browser interface and handles user interactions
- Location: `templates/index.html`
- Contains: HTML structure, inline CSS styling, inline JavaScript for download triggers and alert auto-hide
- Depends on: Flask Jinja2 template engine, route data passed from the application layer
- Used by: End users via browser

**Application Layer (Routes & Logic):**
- Purpose: Handles HTTP requests, filesystem operations, file serving
- Location: `network_file_server.py`
- Contains: Flask route handlers, utility functions, CLI argument parsing, server startup
- Depends on: Flask, Werkzeug, Python stdlib (os, socket, argparse, pathlib, mimetypes)
- Used by: Presentation layer (template rendering), API consumers (JSON endpoint)

**Data Layer (Filesystem):**
- Purpose: Stores and provides files for browsing, download, and upload
- Location: User-specified directory passed as CLI argument
- Contains: Arbitrary user files
- Depends on: Host operating system filesystem
- Used by: Application layer via `os.listdir()`, `os.path`, `send_file()`

## Data Flow

**File Browsing (GET /):**

1. User navigates to root URL
2. `index()` route handler reads `SHARED_FOLDER` global variable
3. `os.listdir()` enumerates files in the shared directory
4. Each file gets metadata via `get_file_size()` and `get_file_icon()`
5. File list is sorted alphabetically by name (case-insensitive)
6. `render_template('index.html')` renders the page with file data

**File Download (GET /download/<filename>):**

1. User clicks file card or download button in the UI
2. JavaScript `downloadFile()` redirects browser to `/download/<filename>`
3. `download_file()` route handler sanitizes filename via `secure_filename()`
4. File existence is verified on disk
5. `send_file()` streams the file as an attachment to the browser

**File Upload (POST /upload):**

1. User selects a file via the HTML file input and submits the form
2. `upload_file()` route handler extracts the file from `request.files`
3. Filename is sanitized via `secure_filename()`
4. Duplicate check: if file already exists, upload is rejected with a warning flash
5. File is saved to `SHARED_FOLDER` via `file.save()`
6. User is redirected back to index with a success/error flash message

**API File Listing (GET /api/files):**

1. External client requests `/api/files`
2. `api_files()` handler enumerates files identically to the index route
3. Returns JSON response with `{'files': [...]}` payload

**State Management:**
- `SHARED_FOLDER` is a module-level global variable set once during `main()` startup
- No session state, no user accounts, no persistent server state
- Flash messages use Flask's session-based flash mechanism (cookie-backed)

## Key Abstractions

**File Metadata Dictionary:**
- Purpose: Represents a file entry for display in the UI and API responses
- Examples: Built inline in `network_file_server.py` lines 69-74 and 147-152
- Pattern: Dict with keys `name`, `size`, `icon`, `path`; constructed per-file during directory listing

**Utility Functions:**
- `get_local_ip()` at `network_file_server.py:22` - Discovers LAN IP via UDP socket trick
- `get_file_size()` at `network_file_server.py:34` - Converts byte count to human-readable string
- `get_file_icon()` at `network_file_server.py:43` - Maps file extensions to emoji icons via static dict

## Entry Points

**Primary Entry Point (`network_file_server.py`):**
- Location: `network_file_server.py:205` (`if __name__ == '__main__': main()`)
- Triggers: Direct execution via `python network_file_server.py <folder> [--port N] [--host H] [--debug]`
- Responsibilities: Parse CLI args, validate folder path, set global state, print server info, start Flask dev server

**Shell Wrapper (`start_server.sh`):**
- Location: `start_server.sh`
- Triggers: `./start_server.sh <folder> [port]`
- Responsibilities: Check Python availability, verify folder exists, install Flask if missing, invoke `network_file_server.py` with default port 6969

**Placeholder Entry Point (`main.py`):**
- Location: `main.py`
- Triggers: Not currently used in the application flow
- Responsibilities: Prints "Hello from network-file-server!" -- this is a uv-generated scaffold, not the real entry point

## HTTP Routes

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/` | `index()` | Render file browser HTML page |
| GET | `/download/<filename>` | `download_file()` | Stream file as attachment download |
| POST | `/upload` | `upload_file()` | Accept file upload via multipart form |
| GET | `/api/files` | `api_files()` | Return file list as JSON |

## Error Handling

**Strategy:** Flash messages for user-facing errors, HTTP status codes for API errors, `sys.exit(1)` for fatal startup errors.

**Patterns:**
- Route handlers catch broad `Exception` and surface errors via `flash()` + redirect to index
- `PermissionError` is caught specifically during directory listing
- API route returns JSON error with appropriate HTTP status codes (404, 403)
- CLI startup validates folder existence, directory type, and read permissions before starting the server; exits with error message on failure
- Bare `except:` clause in `get_local_ip()` silently falls back to `127.0.0.1`

## Cross-Cutting Concerns

**Logging:** No structured logging. Uses `print()` statements for server startup info. No request logging beyond Flask's built-in dev server output.

**Validation:** Filename sanitization via `werkzeug.utils.secure_filename()` on both upload and download paths. Folder path validated at startup only.

**Authentication:** None. No authentication or authorization. Any device on the local network can browse, download, and upload files.

**Security:** Relies entirely on network-level isolation (same WiFi). `app.secret_key` is hardcoded as `'your-secret-key-change-this'` in `network_file_server.py:17`.

---

*Architecture analysis: 2026-03-09*
