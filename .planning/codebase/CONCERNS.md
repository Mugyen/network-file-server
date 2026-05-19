# Codebase Concerns

Technical debt, known issues, and areas of concern for the Network File Server codebase.

## Security Concerns

### Hardcoded Secret Key (Critical)
- **File:** `network_file_server.py:17`
- **Issue:** `app.secret_key = 'your-secret-key-change-this'` — Flask secret key is hardcoded and predictable
- **Impact:** Session cookies can be forged, flash messages can be tampered with
- **Fix:** Generate random secret key at runtime or load from environment variable

### Path Traversal Risk (Medium)
- **File:** `network_file_server.py:91`
- **Issue:** Uses `secure_filename()` which mitigates most path traversal, but the server serves any file in the shared folder without authentication
- **Impact:** Anyone on the network can download/upload files
- **Note:** This may be intentional for a LAN file sharing tool, but there's no opt-in authentication

### No Upload Size Limit (Medium)
- **File:** `network_file_server.py:103-134`
- **Issue:** No `MAX_CONTENT_LENGTH` set on Flask app — uploads are unbounded
- **Impact:** A single large upload could exhaust disk space or memory

### Bare Exception Handling (Low)
- **File:** `network_file_server.py:31`
- **Issue:** `except:` (bare except) in `get_local_ip()` silently catches all exceptions
- **Impact:** Hides real errors; should catch `socket.error` or `OSError` specifically

## Technical Debt

### Global Mutable State
- **File:** `network_file_server.py:19`
- **Issue:** `SHARED_FOLDER = None` as a global variable, mutated in `main()`
- **Impact:** Makes testing difficult, prevents running multiple instances, not thread-safe

### Flat File Listing Only
- **File:** `network_file_server.py:57-82`
- **Issue:** Only lists files in the root of `SHARED_FOLDER` — no subdirectory navigation
- **Impact:** Users can't browse folder hierarchies

### Duplicated File Listing Logic
- **Files:** `network_file_server.py:64-74` and `network_file_server.py:143-152`
- **Issue:** `index()` and `api_files()` have identical file listing logic copy-pasted
- **Impact:** Bug fixes need to be applied in two places

### Unused Entry Point
- **File:** `main.py`
- **Issue:** `main.py` just prints "Hello from network-file-server!" — not connected to actual server
- **Impact:** Confusing; `pyproject.toml` may point to wrong entry point

### Shell Script Bypasses uv
- **File:** `start_server.sh`
- **Issue:** Uses `python3` and `pip3` directly instead of `uv` (project has `pyproject.toml` and `uv.lock`)
- **Impact:** Dependencies may not match locked versions; inconsistent with project's dependency management

## Performance Concerns

### Synchronous File Operations
- **File:** `network_file_server.py`
- **Issue:** All file I/O is synchronous via Flask's built-in server
- **Impact:** Large file downloads block the server for other users
- **Note:** Acceptable for small LAN use, but won't scale

### No Caching
- **Issue:** File listings are regenerated on every request, file metadata re-read each time
- **Impact:** Slight overhead for directories with many files

## Fragile Areas

### IP Detection
- **File:** `network_file_server.py:22-30`
- **Issue:** Connects to `8.8.8.8:80` to detect local IP — fails if no internet connection
- **Impact:** Server still works on `localhost`, but displayed URL will be wrong

### No Graceful Shutdown
- **File:** `network_file_server.py:197-203`
- **Issue:** `KeyboardInterrupt` is caught but no cleanup performed (e.g., in-progress uploads)
- **Impact:** Interrupted uploads may leave partial files

---
*Generated: 2026-03-09*
