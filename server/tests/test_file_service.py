import os
from pathlib import Path

import pytest

from server.app.exceptions import PathTraversalError
from server.app.models.enums import FileType
from server.app.services.file_service import (
    format_file_size,
    list_directory,
    resolve_safe_path,
)


class TestResolveSafePath:
    """Tests for resolve_safe_path -- path traversal guard."""

    def test_valid_file_in_base(self, tmp_shared_folder: Path) -> None:
        result = resolve_safe_path(tmp_shared_folder, "test.txt")
        assert result == tmp_shared_folder / "test.txt"
        assert result.exists()

    def test_valid_file_in_subdirectory(self, tmp_shared_folder: Path) -> None:
        result = resolve_safe_path(tmp_shared_folder, "subdir/nested.txt")
        assert result == tmp_shared_folder / "subdir" / "nested.txt"

    def test_parent_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            resolve_safe_path(tmp_shared_folder, "../etc/passwd")

    def test_nested_parent_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            resolve_safe_path(tmp_shared_folder, "subdir/../../etc/passwd")

    def test_absolute_path_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            resolve_safe_path(tmp_shared_folder, "/etc/passwd")

    def test_traversal_that_stays_within_base(
        self, tmp_shared_folder: Path
    ) -> None:
        """valid/../valid/file.txt should resolve correctly if it stays in base."""
        result = resolve_safe_path(tmp_shared_folder, "subdir/../subdir/nested.txt")
        assert result == (tmp_shared_folder / "subdir" / "nested.txt").resolve()

    def test_symlink_outside_base_raises(self, tmp_shared_folder: Path) -> None:
        """A symlink pointing outside the base directory must be rejected."""
        link_path = tmp_shared_folder / "evil_link"
        link_path.symlink_to("/etc")
        with pytest.raises(PathTraversalError):
            resolve_safe_path(tmp_shared_folder, "evil_link")

    def test_nonexistent_file_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(FileNotFoundError):
            resolve_safe_path(tmp_shared_folder, "nonexistent.txt")

    def test_empty_path_resolves_to_base(self, tmp_shared_folder: Path) -> None:
        """Empty string should resolve to the base directory itself."""
        result = resolve_safe_path(tmp_shared_folder, "")
        assert result == tmp_shared_folder.resolve()

    def test_directory_resolves(self, tmp_shared_folder: Path) -> None:
        result = resolve_safe_path(tmp_shared_folder, "subdir")
        assert result == (tmp_shared_folder / "subdir").resolve()
        assert result.is_dir()


class TestListDirectory:
    """Tests for list_directory."""

    def test_list_root_directory(self, tmp_shared_folder: Path) -> None:
        result = list_directory(tmp_shared_folder, "")
        assert result.path == ""
        names = {e.name for e in result.entries}
        assert "test.txt" in names
        assert "subdir" in names
        assert "empty_dir" in names

    def test_list_root_entry_types(self, tmp_shared_folder: Path) -> None:
        result = list_directory(tmp_shared_folder, "")
        entries_by_name = {e.name: e for e in result.entries}
        assert entries_by_name["test.txt"].type == FileType.FILE
        assert entries_by_name["subdir"].type == FileType.DIRECTORY
        assert entries_by_name["empty_dir"].type == FileType.DIRECTORY

    def test_list_root_entry_fields(self, tmp_shared_folder: Path) -> None:
        result = list_directory(tmp_shared_folder, "")
        entries_by_name = {e.name: e for e in result.entries}
        txt_entry = entries_by_name["test.txt"]
        assert txt_entry.size == len("hello world")
        assert isinstance(txt_entry.size_display, str)
        assert len(txt_entry.size_display) > 0
        assert isinstance(txt_entry.modified, str)
        # ISO 8601 format check: contains T separator
        assert "T" in txt_entry.modified

    def test_list_subdirectory(self, tmp_shared_folder: Path) -> None:
        result = list_directory(tmp_shared_folder, "subdir")
        assert result.path == "subdir"
        names = {e.name for e in result.entries}
        assert "nested.txt" in names

    def test_list_directory_traversal_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(PathTraversalError):
            list_directory(tmp_shared_folder, "../")

    def test_list_empty_directory(self, tmp_shared_folder: Path) -> None:
        result = list_directory(tmp_shared_folder, "empty_dir")
        assert result.path == "empty_dir"
        assert len(result.entries) == 0


class TestFormatFileSize:
    """Tests for format_file_size helper."""

    def test_bytes(self) -> None:
        assert format_file_size(500) == "500.0 B"

    def test_kilobytes(self) -> None:
        assert format_file_size(1024) == "1.0 KB"

    def test_megabytes(self) -> None:
        assert format_file_size(1048576) == "1.0 MB"

    def test_gigabytes(self) -> None:
        assert format_file_size(1073741824) == "1.0 GB"

    def test_terabytes(self) -> None:
        assert format_file_size(1099511627776) == "1.0 TB"

    def test_zero(self) -> None:
        assert format_file_size(0) == "0.0 B"
