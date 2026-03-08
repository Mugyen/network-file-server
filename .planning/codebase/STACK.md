# Technology Stack

**Analysis Date:** 2026-03-09

## Languages

**Primary:**
- Python 3.11 - All server logic, CLI, file operations (`wifi_file_server.py`, `main.py`)

**Secondary:**
- HTML/CSS/JavaScript - Single-page web UI (`templates/index.html`), inline styles and scripts, no build step
- Bash - Startup helper script (`start_server.sh`)

## Runtime

**Environment:**
- Python 3.11 (pinned in `.python-version`)
- CPython (standard interpreter)

**Package Manager:**
- uv - Primary dependency manager; lockfile present at `uv.lock`
- pip - Referenced in `README.md` and `start_server.sh` as alternative install path
- Lockfile: `uv.lock` present and committed

## Frameworks

**Core:**
- Flask 3.1.2 - HTTP server, routing, template rendering, file serving (`wifi_file_server.py`)
- Jinja2 (transitive via Flask) - HTML templating (`templates/index.html`)
- Werkzeug (transitive via Flask) - WSGI utilities, `secure_filename` for upload safety

**Testing:**
- None detected - No test framework configured

**Build/Dev:**
- No build tools - Plain Python, no compilation step
- No linters or formatters configured

## Key Dependencies

**Critical:**
- `flask>=3.1.2` - The entire application is a Flask server; specified in `pyproject.toml`
- `werkzeug` - Provides `secure_filename()` for upload path sanitization in `wifi_file_server.py` line 91, 120

**Infrastructure (transitive via Flask):**
- `blinker` 1.9.0 - Flask signal support
- `click` 8.3.1 - Flask CLI support
- `itsdangerous` - Session cookie signing (Flask secret key)
- `jinja2` - Template engine for `templates/index.html`
- `markupsafe` - HTML escaping for Jinja2

**Note:** `requirements.txt` pins Flask==2.3.3 and Werkzeug==2.3.7, while `pyproject.toml` specifies `flask>=3.1.2`. The `uv.lock` resolves to Flask 3.1.2. The `requirements.txt` is stale and conflicts with `pyproject.toml`.

## Standard Library Usage

Key stdlib modules used in `wifi_file_server.py`:
- `os` - File system operations (listdir, path checks, getsize)
- `sys` - Exit codes
- `argparse` - CLI argument parsing (folder, port, host, debug flags)
- `mimetypes` - Imported but not actively used in current code
- `pathlib.Path` - File extension extraction in `get_file_icon()`
- `socket` - Local IP address discovery via UDP socket trick in `get_local_ip()`

## Configuration

**Environment:**
- No `.env` file present - No environment variables used
- Flask secret key is hardcoded in `wifi_file_server.py` line 17: `app.secret_key = 'your-secret-key-change-this'`
- All configuration is via CLI arguments to `wifi_file_server.py`

**CLI Arguments (defined in `wifi_file_server.py` lines 163-167):**
- `folder` (required) - Path to directory to share
- `--port` / `-p` (default: 5000) - Server port
- `--host` (default: 0.0.0.0) - Bind address
- `--debug` (flag) - Flask debug mode

**Build:**
- `pyproject.toml` - Project metadata and dependency declaration
- No build configuration needed; runs directly as a Python script

## Platform Requirements

**Development:**
- Python 3.11+
- uv package manager (preferred) or pip
- No OS-specific requirements; uses cross-platform Python APIs

**Production:**
- Runs on Flask's built-in Werkzeug development server (no production WSGI server like gunicorn configured)
- Binds to 0.0.0.0 by default for LAN access
- Default port: 5000 (CLI), 6969 (`start_server.sh`)
- Requires read access to the shared folder; write access needed for uploads

---

*Stack analysis: 2026-03-09*
