"""Tests for shared.spa — SPA shell response helper."""

from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse

from shared.spa import SPA_PLACEHOLDER_HTML, spa_shell_response


def test_serves_index_when_present(tmp_path: Path) -> None:
    """An existing index.html is served as a FileResponse with text/html."""
    index = tmp_path / "index.html"
    index.write_text("<!doctype html><html><body>built</body></html>")
    resp = spa_shell_response(index)
    assert isinstance(resp, FileResponse)
    assert resp.path == str(index)
    assert resp.media_type == "text/html"


def test_serves_placeholder_when_index_missing(tmp_path: Path) -> None:
    """A missing index.html falls back to the placeholder shell."""
    resp = spa_shell_response(tmp_path / "index.html")
    assert isinstance(resp, HTMLResponse)
    assert resp.body.decode() == SPA_PLACEHOLDER_HTML


def test_serves_placeholder_when_index_is_directory(tmp_path: Path) -> None:
    """A directory at the index path is not a bundle — fall back."""
    (tmp_path / "index.html").mkdir()
    resp = spa_shell_response(tmp_path / "index.html")
    assert isinstance(resp, HTMLResponse)


def test_placeholder_has_root_div() -> None:
    """The placeholder must contain the React mount point."""
    assert "<div id='root'>" in SPA_PLACEHOLDER_HTML
