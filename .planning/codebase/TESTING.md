# Testing Patterns

**Analysis Date:** 2026-03-09

## Test Framework

**Runner:**
- No test framework is configured or installed.
- No test runner (pytest, unittest, nose) in `pyproject.toml` dependencies or `requirements.txt`.
- No `pytest.ini`, `conftest.py`, `tox.ini`, or `setup.cfg` with test configuration.

**Recommended Setup (per project `CLAUDE.md` instructions):**
- Use `pytest` as the test runner.
- Add `pytest` to `pyproject.toml` dev dependencies.
- Use `uv` to manage and run tests: `uv run pytest`.

**Assertion Library:**
- Not configured. Use pytest's built-in `assert` statements.

**Run Commands (to be established):**
```bash
uv run pytest                  # Run all tests
uv run pytest -x               # Stop on first failure
uv run pytest --cov             # Coverage report
uv run pytest tests/            # Run specific directory
```

## Test File Organization

**Location:**
- No test files exist anywhere in the project.
- No `tests/` directory.

**Recommended Structure:**
```
tests/
  __init__.py
  conftest.py               # Shared fixtures (Flask test client, temp directories)
  test_wifi_file_server.py  # Tests for wifi_file_server.py
```

**Naming:**
- Use `test_` prefix for test files: `test_wifi_file_server.py`
- Use `test_` prefix for test functions: `test_get_file_size_returns_bytes()`

## Test Structure

**No existing tests.** The following patterns should be established when adding tests.

**Recommended Suite Organization:**
```python
import pytest
from wifi_file_server import app, get_file_size, get_file_icon, get_local_ip


class TestGetFileSize:
    """Tests for the get_file_size utility function."""

    def test_returns_bytes_for_small_file(self, tmp_path: Path) -> None:
        f = tmp_path / "small.txt"
        f.write_text("hello")
        result = get_file_size(str(f))
        assert result == "5.0 B"

    def test_returns_kb_for_kilobyte_file(self, tmp_path: Path) -> None:
        f = tmp_path / "medium.txt"
        f.write_bytes(b"x" * 2048)
        result = get_file_size(str(f))
        assert result == "2.0 KB"


class TestGetFileIcon:
    """Tests for the get_file_icon utility function."""

    def test_returns_python_icon_for_py_file(self) -> None:
        assert get_file_icon("script.py") == "\U0001f40d"

    def test_returns_default_icon_for_unknown_extension(self) -> None:
        assert get_file_icon("file.xyz") == "\U0001f4c4"
```

**Patterns:**
- Group related tests in classes prefixed with `Test`.
- Use descriptive function names: `test_<what>_<condition>_<expected>`.
- One assertion per test where practical.
- Use `tmp_path` fixture (built-in pytest) for filesystem tests.

## Mocking

**Framework:** Use `unittest.mock` (stdlib) or `pytest-mock`.

**Recommended Patterns:**
```python
from unittest.mock import patch, MagicMock


class TestGetLocalIp:
    """Tests for the get_local_ip utility function."""

    @patch("wifi_file_server.socket.socket")
    def test_returns_local_ip_on_success(self, mock_socket_class: MagicMock) -> None:
        mock_socket = MagicMock()
        mock_socket.getsockname.return_value = ("192.168.1.100", 0)
        mock_socket_class.return_value = mock_socket
        result = get_local_ip()
        assert result == "192.168.1.100"

    @patch("wifi_file_server.socket.socket")
    def test_returns_localhost_on_failure(self, mock_socket_class: MagicMock) -> None:
        mock_socket_class.side_effect = OSError("Network unreachable")
        result = get_local_ip()
        assert result == "127.0.0.1"
```

**What to Mock:**
- Network calls (`socket.socket` in `get_local_ip()`)
- Filesystem operations when testing route logic (use `tmp_path` fixture instead where possible)
- Flask's `flash()` to verify error messages

**What NOT to Mock:**
- `get_file_size()`, `get_file_icon()` -- these are pure/near-pure functions; test with real data.
- Flask test client -- use `app.test_client()` for integration-level route tests.

## Fixtures and Factories

**Recommended Flask Test Client Fixture:**
```python
import pytest
from pathlib import Path
from wifi_file_server import app


@pytest.fixture
def shared_folder(tmp_path: Path) -> Path:
    """Create a temporary shared folder with sample files."""
    sample = tmp_path / "test_file.txt"
    sample.write_text("sample content")
    return tmp_path


@pytest.fixture
def client(shared_folder: Path):
    """Flask test client with SHARED_FOLDER configured."""
    import wifi_file_server
    wifi_file_server.SHARED_FOLDER = str(shared_folder)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
```

**Location:**
- Place shared fixtures in `tests/conftest.py`.
- Place test-specific fixtures within test files.

## Coverage

**Requirements:** Not enforced. No coverage tool configured.

**Recommended Setup:**
- Add `pytest-cov` to dev dependencies.
- Run: `uv run pytest --cov=. --cov-report=term-missing`

**Priority areas for coverage (by risk):**
1. `upload_file()` in `wifi_file_server.py` (lines 103-134) -- handles user file uploads, security-sensitive
2. `download_file()` in `wifi_file_server.py` (lines 84-101) -- serves files, path traversal risk
3. `index()` in `wifi_file_server.py` (lines 57-82) -- main page rendering, filesystem interaction
4. `api_files()` in `wifi_file_server.py` (lines 136-157) -- JSON API, error handling
5. `get_file_size()` in `wifi_file_server.py` (lines 34-41) -- unit conversion logic
6. `get_file_icon()` in `wifi_file_server.py` (lines 43-55) -- extension mapping

## Test Types

**Unit Tests:**
- Target: utility functions (`get_file_size`, `get_file_icon`, `get_local_ip`)
- Approach: Direct function calls with known inputs, assert outputs.
- No external dependencies needed for `get_file_icon`. Use `tmp_path` for `get_file_size`.

**Integration Tests:**
- Target: Flask route handlers (`index`, `download_file`, `upload_file`, `api_files`)
- Approach: Use `app.test_client()` to make HTTP requests, assert response status codes, content, and flash messages.
- Requires: `SHARED_FOLDER` global set to a `tmp_path` directory.

**E2E Tests:**
- Not implemented. Per project `CLAUDE.md`, browser-based testing should be done for UI elements.
- Consider Selenium or Playwright for testing the file upload/download UI in `templates/index.html`.

## Common Patterns

**Recommended Async Testing:** Not applicable -- Flask routes are synchronous in this codebase.

**Recommended Route Testing:**
```python
class TestIndexRoute:
    """Tests for the index route."""

    def test_index_returns_200(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_index_lists_files(self, client, shared_folder: Path) -> None:
        response = client.get("/")
        assert b"test_file.txt" in response.data

    def test_index_shows_error_when_folder_missing(self, client) -> None:
        import wifi_file_server
        wifi_file_server.SHARED_FOLDER = "/nonexistent/path"
        response = client.get("/")
        assert response.status_code == 200  # Still renders, with flash message
```

**Recommended Upload Testing:**
```python
class TestUploadRoute:
    """Tests for the file upload route."""

    def test_upload_saves_file(self, client, shared_folder: Path) -> None:
        from io import BytesIO
        data = {"file": (BytesIO(b"file content"), "uploaded.txt")}
        response = client.post("/upload", data=data, content_type="multipart/form-data")
        assert response.status_code == 302  # Redirect after upload
        assert (shared_folder / "uploaded.txt").exists()

    def test_upload_rejects_duplicate_filename(self, client, shared_folder: Path) -> None:
        (shared_folder / "existing.txt").write_text("already here")
        from io import BytesIO
        data = {"file": (BytesIO(b"new content"), "existing.txt")}
        response = client.post("/upload", data=data, content_type="multipart/form-data")
        assert response.status_code == 302
        # Original file content should be unchanged
        assert (shared_folder / "existing.txt").read_text() == "already here"
```

**Recommended Error Testing:**
```python
class TestDownloadRoute:
    """Tests for the file download route."""

    def test_download_nonexistent_file_redirects(self, client) -> None:
        response = client.get("/download/nonexistent.txt")
        assert response.status_code == 302

    def test_download_existing_file_returns_content(self, client, shared_folder: Path) -> None:
        response = client.get("/download/test_file.txt")
        assert response.status_code == 200
```

**Recommended API Testing:**
```python
class TestApiFilesRoute:
    """Tests for the API file listing route."""

    def test_api_files_returns_json(self, client) -> None:
        response = client.get("/api/files")
        assert response.status_code == 200
        data = response.get_json()
        assert "files" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "test_file.txt"

    def test_api_files_returns_404_when_folder_missing(self, client) -> None:
        import wifi_file_server
        wifi_file_server.SHARED_FOLDER = "/nonexistent"
        response = client.get("/api/files")
        assert response.status_code == 404
```

## Current State Summary

The project has **zero test coverage**. No test framework, no test files, no CI pipeline. All patterns above are recommended based on the codebase structure and project instructions in `CLAUDE.md`. When implementing tests:

1. Add `pytest` and `pytest-cov` to `pyproject.toml` under dev dependencies.
2. Create `tests/` directory with `__init__.py` and `conftest.py`.
3. Start with unit tests for `get_file_size()` and `get_file_icon()` (simplest, no mocking needed).
4. Add integration tests for route handlers using Flask test client.
5. Use `uv` to run all tests: `uv run pytest`.

---

*Testing analysis: 2026-03-09*
