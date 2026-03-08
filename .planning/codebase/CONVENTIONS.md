# Coding Conventions

**Analysis Date:** 2026-03-09

## Naming Patterns

**Files:**
- Python source files use `snake_case`: `wifi_file_server.py`, `main.py`
- Single HTML template: `templates/index.html`
- Shell scripts use `snake_case`: `start_server.sh`

**Functions:**
- Use `snake_case` for all functions: `get_local_ip()`, `get_file_size()`, `download_file()`
- Prefix utility/helper functions with `get_`: `get_local_ip()`, `get_file_size()`, `get_file_icon()`
- Route handler functions match their route purpose: `index()`, `download_file()`, `upload_file()`, `api_files()`

**Variables:**
- Use `snake_case` for local variables: `file_path`, `folder_path`, `local_ip`
- Use `UPPER_SNAKE_CASE` for module-level globals: `SHARED_FOLDER`

**Types:**
- No type annotations are used anywhere in the codebase. Functions lack parameter type hints and return type hints.
- When adding new code, add strict type annotations per project instructions (see `CLAUDE.md`).

## Code Style

**Formatting:**
- No formatter configured (no `.prettierrc`, `pyproject.toml [tool.black]`, `setup.cfg`, or `.flake8`).
- Indentation: 4 spaces (standard Python).
- String formatting: f-strings throughout (`f"Error: Folder '{folder_path}' does not exist"`).
- Use f-strings for all string interpolation when adding new code.

**Linting:**
- No linter configured. No flake8, pylint, ruff, or mypy configuration present.
- When adding new code, follow PEP 8 conventions as observed in the existing source.

**Line Length:**
- No explicit limit configured. Longest lines in `wifi_file_server.py` are ~95 characters (the Flask import line at line 12).
- Keep lines under 100 characters.

## Import Organization

**Order (observed in `wifi_file_server.py`):**
1. Standard library modules (`os`, `sys`, `argparse`, `mimetypes`, `socket`)
2. Third-party framework imports (`from pathlib import Path`)
3. Third-party packages (`flask`, `werkzeug`)

**Style:**
- Use `import module` for standard library: `import os`, `import sys`
- Use `from module import names` for specific items: `from flask import Flask, render_template, ...`
- Use `from module import name` for single items: `from werkzeug.utils import secure_filename`
- `pathlib.Path` is imported via `from pathlib import Path` but used sparingly -- most file operations use `os.path` instead.

**Path Aliases:**
- None configured. No `sys.path` manipulation or namespace packages.

## Error Handling

**Patterns:**
- Flask route handlers use `flash()` with category strings (`"error"`, `"warning"`, `"success"`) to communicate errors to users via the web UI.
- API endpoints return `jsonify({'error': '...'})` with appropriate HTTP status codes (404, 403).
- The `main()` function uses `sys.exit(1)` for fatal startup errors (missing folder, bad permissions).
- Bare `except:` is used in `get_local_ip()` (line 31) -- avoid this pattern. Always catch specific exceptions.
- `except Exception as e:` is used as a catch-all for file operations (lines 99, 131, 201).
- `except PermissionError:` is used for specific filesystem permission errors (lines 75, 153).

**Error flow in route handlers:**
```python
# Pattern: validate state, flash error, redirect
if not SHARED_FOLDER:
    flash("Shared folder not configured", "error")
    return redirect(url_for('index'))
```

**Error flow in API handlers:**
```python
# Pattern: validate state, return JSON error with status code
if not SHARED_FOLDER or not os.path.exists(SHARED_FOLDER):
    return jsonify({'error': 'Shared folder not found'}), 404
```

**When adding new code:** Raise typed exceptions instead of returning None/empty values. Catch specific exception types rather than bare `except:` or `except Exception`.

## Logging

**Framework:** No logging framework. Uses `print()` statements for server startup messages (lines 190-195 in `wifi_file_server.py`).

**Patterns:**
- `print()` with emoji prefixes for startup info: `print(f"\n{emoji} WiFi File Server Starting...")`
- `flash()` for user-facing web messages.
- No structured logging, no log levels, no log files.

## Comments

**When to Comment:**
- Module-level docstring at top of `wifi_file_server.py` (lines 2-5): brief description of purpose.
- Every function has a one-line docstring: `"""Get human readable file size"""`
- Inline comments for non-obvious logic: `# Connect to a remote server to get local IP` (line 25), `# Sort files by name` (line 79).

**Docstrings:**
- Single-line triple-quoted strings for all functions.
- No parameter documentation, no return type documentation.
- When adding new code, include parameter and return type documentation in docstrings.

## Function Design

**Size:** Functions are small, typically 10-25 lines. The longest function is `main()` at ~45 lines.

**Parameters:** Functions take simple positional parameters without type annotations. No default parameters in utility functions. The `argparse` configuration in `main()` uses defaults for CLI arguments (`default=5000`, `default='0.0.0.0'`).

**Return Values:**
- Helper functions return computed values directly: `get_file_size()` returns a formatted string, `get_file_icon()` returns an emoji string.
- Route handlers return Flask response objects (`render_template(...)`, `redirect(...)`, `send_file(...)`, `jsonify(...)`).
- `get_local_ip()` falls back to `"127.0.0.1"` on any exception -- this masks errors silently.

## Module Design

**Exports:** No `__all__` defined. The codebase is a single-module application with no internal imports between modules.

**Barrel Files:** Not used. The project has only two Python files at root level.

**Application Structure:**
- `wifi_file_server.py`: Contains all application logic -- Flask app creation, route handlers, utility functions, CLI argument parsing, and server startup. This is a monolithic single-file application.
- `main.py`: Stub entry point (prints "Hello from wifi-ftp-server!"). Not connected to the actual application.

## Global State

**Pattern:** The module uses a global variable `SHARED_FOLDER` (line 20) set via the `main()` function. Route handlers read this global directly. This is a common Flask pattern for simple applications but does not scale well.

## Template Patterns

**Jinja2 Templates:**
- Templates live in `templates/` directory (Flask default).
- Single template: `templates/index.html`.
- Inline CSS within `<style>` tags (no separate CSS files).
- Inline JavaScript within `<script>` tags (no separate JS files).
- Template variables passed via `render_template()`: `files`, `folder_path`.
- Flash messages rendered via `get_flashed_messages(with_categories=true)`.

## Security Patterns

**Filename Sanitization:** Uses `werkzeug.utils.secure_filename()` for all uploaded filenames and download path construction (lines 91, 120).

**Path Traversal Prevention:** Filenames are sanitized before joining with `SHARED_FOLDER` via `os.path.join()`. No explicit path traversal checks beyond `secure_filename()`.

**Secret Key:** Hardcoded `app.secret_key = 'your-secret-key-change-this'` (line 17). This should be changed for any deployment.

---

*Convention analysis: 2026-03-09*
