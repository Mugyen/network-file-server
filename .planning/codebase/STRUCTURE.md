# Codebase Structure

**Analysis Date:** 2026-03-09

## Directory Layout

```
network-file-server/
├── .gitignore              # Python bytecode, build artifacts, .venv
├── .python-version         # Python 3.11 (used by uv)
├── .planning/              # GSD planning documents
│   └── codebase/           # Codebase analysis documents
├── feature-ideas/          # 35 feature proposal markdown files
│   ├── 01-qr-code-connect.md
│   ├── ...
│   └── 35-integrity-verification.md
├── templates/              # Flask Jinja2 HTML templates
│   └── index.html          # Single-page file browser UI
├── main.py                 # uv scaffold placeholder (NOT the real entry point)
├── network_file_server.py     # Entire application: routes, logic, CLI, server
├── start_server.sh         # Shell wrapper script for quick startup
├── pyproject.toml          # uv project config (name, version, dependencies)
├── requirements.txt        # pip-style dependencies (Flask, Werkzeug)
├── uv.lock                 # uv lockfile
└── README.md               # Project documentation
```

## Directory Purposes

**`templates/`:**
- Purpose: Flask Jinja2 template directory (Flask convention)
- Contains: Single HTML file with inline CSS and JavaScript
- Key files: `templates/index.html` -- the complete web UI

**`feature-ideas/`:**
- Purpose: Feature proposals and design documents for future development
- Contains: 35 numbered markdown files, each describing a potential feature
- Key files: Numbered `01-*` through `35-*`, covering topics from QR codes to file versioning

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Contains: Generated analysis markdown files
- Key files: Files in `.planning/codebase/`

## Key File Locations

**Entry Points:**
- `network_file_server.py`: The real application entry point (run directly with `python network_file_server.py <folder>`)
- `start_server.sh`: Shell convenience wrapper that validates environment and invokes `network_file_server.py`
- `main.py`: uv-generated placeholder; does not participate in the application

**Configuration:**
- `pyproject.toml`: Project metadata and uv dependency declaration (Flask >= 3.1.2)
- `requirements.txt`: pip-compatible dependency list (Flask 2.3.3, Werkzeug 2.3.7) -- note version mismatch with pyproject.toml
- `.python-version`: Pins Python 3.11
- `uv.lock`: Locked dependency resolution

**Core Logic:**
- `network_file_server.py:22-55`: Utility functions (`get_local_ip`, `get_file_size`, `get_file_icon`)
- `network_file_server.py:57-82`: Index route -- file listing and rendering
- `network_file_server.py:84-101`: Download route -- file serving
- `network_file_server.py:103-134`: Upload route -- file receiving
- `network_file_server.py:136-157`: API route -- JSON file listing
- `network_file_server.py:159-206`: CLI parsing and server startup

**Web UI:**
- `templates/index.html:1-289`: CSS styles (inline, no external stylesheet)
- `templates/index.html:291-358`: HTML structure with Jinja2 template tags
- `templates/index.html:361-387`: JavaScript (inline, no external script)

**Testing:**
- No test files exist. No test framework is configured.

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `network_file_server.py`, `main.py`)
- Templates: `lowercase.html` (e.g., `index.html`)
- Shell scripts: `snake_case.sh` (e.g., `start_server.sh`)
- Feature docs: `NN-kebab-case.md` (e.g., `01-qr-code-connect.md`)

**Directories:**
- All lowercase, no separators: `templates/`, `feature-ideas/` (exception uses hyphen)

**Functions:**
- Python: `snake_case` (e.g., `get_file_size`, `download_file`, `upload_file`)

**Routes:**
- URL paths: lowercase with hyphens not used; simple paths like `/download/<filename>`, `/upload`, `/api/files`

## Where to Add New Code

**New Route/Endpoint:**
- Add to `network_file_server.py` alongside existing `@app.route()` handlers
- Follow the existing pattern: decorator, docstring, guard clause checking `SHARED_FOLDER`, try/except with flash messages

**New Template Page:**
- Add to `templates/` directory as a new `.html` file
- Follow Flask Jinja2 conventions; reference via `render_template('newpage.html')`

**New Utility Function:**
- Add to `network_file_server.py` in the utility section (lines 22-55, before route handlers)
- When the file grows, consider extracting into a `utils.py` module

**New Feature Module:**
- Currently no module structure exists; everything is in `network_file_server.py`
- For significant features, create a new Python module at the project root (e.g., `auth.py`, `api.py`) and import into `network_file_server.py`
- Alternatively, create a `src/` or package directory if the project grows beyond 2-3 modules

**New Static Assets (CSS/JS):**
- Currently all styles and scripts are inline in `templates/index.html`
- To add external assets, create a `static/` directory (Flask convention) with `static/css/` and `static/js/` subdirectories
- Reference via `url_for('static', filename='css/style.css')` in templates

**Tests:**
- No test directory exists yet
- Create `tests/` at the project root
- Name test files `test_<module>.py` (e.g., `tests/test_network_file_server.py`)

## Special Directories

**`feature-ideas/`:**
- Purpose: Product planning documents for future features
- Generated: No (manually authored)
- Committed: Yes (tracked in git)

**`.venv/`:**
- Purpose: Python virtual environment managed by uv
- Generated: Yes (auto-created by uv)
- Committed: No (excluded via `.gitignore`)

**`.planning/`:**
- Purpose: GSD codebase analysis and planning artifacts
- Generated: Yes (by GSD tooling)
- Committed: Intended to be committed

---

*Structure analysis: 2026-03-09*
