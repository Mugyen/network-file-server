from io import BytesIO
from pathlib import Path

import pytest

from server.app.exceptions import (
    FileConflictError,
    InvalidFileNameError,
    InvalidFileRequestError,
    PathTraversalError,
)
from server.app.models.enums import ConflictResolution, FileType
from server.app.services.file_service import (
    create_folder,
    delete_paths,
    download_as_zip,
    download_file,
    format_file_size,
    list_directory,
    rename_path,
    resolve_safe_path,
    upload_file,
    validate_upload_filename,
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


# --- NEW service function tests (Task 1) ---


class FakeUploadFile:
    """A minimal stand-in for FastAPI's UploadFile for unit testing."""

    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._stream = BytesIO(content)
        self.size = len(content)

    async def read(self, size: int) -> bytes:
        return self._stream.read(size)

    async def seek(self, offset: int) -> None:
        self._stream.seek(offset)

    async def close(self) -> None:
        self._stream.close()


class TestUploadFile:
    """Tests for upload_file service function."""

    @pytest.mark.asyncio
    async def test_upload_new_file(self, tmp_shared_folder: Path) -> None:
        fake = FakeUploadFile("newfile.txt", b"file content here")
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.OVERWRITE
        )
        assert result.name == "newfile.txt"
        assert result.size == len(b"file content here")
        assert result.skipped is False
        saved = tmp_shared_folder / "newfile.txt"
        assert saved.exists()
        assert saved.read_bytes() == b"file content here"

    @pytest.mark.asyncio
    async def test_upload_to_subdirectory(self, tmp_shared_folder: Path) -> None:
        fake = FakeUploadFile("sub_upload.txt", b"sub data")
        result = await upload_file(
            tmp_shared_folder, "subdir", fake, ConflictResolution.OVERWRITE
        )
        assert result.name == "sub_upload.txt"
        saved = tmp_shared_folder / "subdir" / "sub_upload.txt"
        assert saved.exists()

    @pytest.mark.asyncio
    async def test_upload_conflict_no_resolution_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        """Uploading a file that already exists without resolution raises FileConflictError."""
        fake = FakeUploadFile("test.txt", b"overwrite attempt")
        with pytest.raises(FileConflictError):
            await upload_file(tmp_shared_folder, "", fake, None)

    @pytest.mark.asyncio
    async def test_upload_overwrite_replaces_file(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("test.txt", b"new content")
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.OVERWRITE
        )
        assert result.name == "test.txt"
        assert result.skipped is False
        assert (tmp_shared_folder / "test.txt").read_bytes() == b"new content"

    @pytest.mark.asyncio
    async def test_upload_rename_appends_suffix(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("test.txt", b"renamed copy")
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.RENAME
        )
        assert result.name == "test_1.txt"
        assert result.skipped is False
        assert (tmp_shared_folder / "test_1.txt").exists()

    @pytest.mark.asyncio
    async def test_upload_rename_increments_suffix(
        self, tmp_shared_folder: Path
    ) -> None:
        (tmp_shared_folder / "test_1.txt").write_text("occupied")
        fake = FakeUploadFile("test.txt", b"renamed again")
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.RENAME
        )
        assert result.name == "test_2.txt"

    @pytest.mark.asyncio
    async def test_upload_skip_returns_skipped(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("test.txt", b"skip me")
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.SKIP
        )
        assert result.skipped is True
        # Original content must remain unchanged
        assert (tmp_shared_folder / "test.txt").read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_upload_path_traversal_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("evil.txt", b"malicious")
        with pytest.raises(PathTraversalError):
            await upload_file(
                tmp_shared_folder, "../outside", fake, ConflictResolution.OVERWRITE
            )

    @pytest.mark.parametrize(
        "filename",
        [
            "",
            ".",
            "..",
            "../escape-upload.txt",
            "subdir/escape-upload.txt",
            "..\\escape-upload.txt",
            "/tmp/escape-upload.txt",
            "C:\\tmp\\escape-upload.txt",
            "bad\x00name.txt",
        ],
    )
    def test_validate_upload_filename_rejects_path_syntax(
        self, filename: str
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            validate_upload_filename(filename)

    @pytest.mark.asyncio
    async def test_upload_rejects_path_bearing_filename(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("../escape-upload.txt", b"malicious")

        with pytest.raises(InvalidFileNameError):
            await upload_file(
                tmp_shared_folder, "", fake, ConflictResolution.OVERWRITE
            )

        assert not (tmp_shared_folder.parent / "escape-upload.txt").exists()

    @pytest.mark.asyncio
    async def test_upload_returns_size_display(
        self, tmp_shared_folder: Path
    ) -> None:
        fake = FakeUploadFile("sized.txt", b"x" * 2048)
        result = await upload_file(
            tmp_shared_folder, "", fake, ConflictResolution.OVERWRITE
        )
        assert result.size_display == "2.0 KB"


class TestDownloadFile:
    """Tests for download_file service function."""

    def test_download_valid_file(self, tmp_shared_folder: Path) -> None:
        result = download_file(tmp_shared_folder, "test.txt")
        assert result == (tmp_shared_folder / "test.txt").resolve()
        assert result.is_file()

    def test_download_directory_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(InvalidFileRequestError, match="directory"):
            download_file(tmp_shared_folder, "subdir")

    def test_download_nonexistent_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(FileNotFoundError):
            download_file(tmp_shared_folder, "nonexistent.txt")

    def test_download_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            download_file(tmp_shared_folder, "../etc/passwd")


class TestDeletePaths:
    """Tests for delete_paths service function."""

    def test_delete_single_file(self, tmp_shared_folder: Path) -> None:
        assert (tmp_shared_folder / "test.txt").exists()
        delete_paths(tmp_shared_folder, ["test.txt"])
        assert not (tmp_shared_folder / "test.txt").exists()

    def test_delete_directory(self, tmp_shared_folder: Path) -> None:
        assert (tmp_shared_folder / "subdir").exists()
        delete_paths(tmp_shared_folder, ["subdir"])
        assert not (tmp_shared_folder / "subdir").exists()

    def test_delete_multiple_paths(self, tmp_shared_folder: Path) -> None:
        delete_paths(tmp_shared_folder, ["test.txt", "empty_dir"])
        assert not (tmp_shared_folder / "test.txt").exists()
        assert not (tmp_shared_folder / "empty_dir").exists()

    def test_delete_nonexistent_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(FileNotFoundError):
            delete_paths(tmp_shared_folder, ["nonexistent.txt"])

    def test_delete_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            delete_paths(tmp_shared_folder, ["../etc/passwd"])


class TestRenamePath:
    """Tests for rename_path service function."""

    def test_rename_file(self, tmp_shared_folder: Path) -> None:
        new_rel = rename_path(tmp_shared_folder, "test.txt", "renamed.txt")
        assert new_rel == "renamed.txt"
        assert (tmp_shared_folder / "renamed.txt").exists()
        assert not (tmp_shared_folder / "test.txt").exists()

    def test_rename_directory(self, tmp_shared_folder: Path) -> None:
        new_rel = rename_path(tmp_shared_folder, "subdir", "newsubdir")
        assert new_rel == "newsubdir"
        assert (tmp_shared_folder / "newsubdir").is_dir()

    def test_rename_nested_file(self, tmp_shared_folder: Path) -> None:
        new_rel = rename_path(tmp_shared_folder, "subdir/nested.txt", "moved.txt")
        assert new_rel == "subdir/moved.txt"
        assert (tmp_shared_folder / "subdir" / "moved.txt").exists()

    def test_rename_conflict_raises(self, tmp_shared_folder: Path) -> None:
        # "subdir" already exists, so renaming test.txt to "subdir" should conflict
        with pytest.raises(FileConflictError):
            rename_path(tmp_shared_folder, "test.txt", "subdir")

    def test_rename_empty_name_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(InvalidFileNameError):
            rename_path(tmp_shared_folder, "test.txt", "")

    def test_rename_slash_in_name_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(InvalidFileNameError):
            rename_path(tmp_shared_folder, "test.txt", "bad/name")

    def test_rename_dotdot_in_name_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(InvalidFileNameError):
            rename_path(tmp_shared_folder, "test.txt", "..")

    def test_rename_null_byte_in_name_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(InvalidFileNameError):
            rename_path(tmp_shared_folder, "test.txt", "bad\x00name")

    def test_rename_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            rename_path(tmp_shared_folder, "../etc/passwd", "newname")


class TestCreateFolder:
    """Tests for create_folder service function."""

    def test_create_folder_in_root(self, tmp_shared_folder: Path) -> None:
        new_rel = create_folder(tmp_shared_folder, "", "newfolder")
        assert new_rel == "newfolder"
        assert (tmp_shared_folder / "newfolder").is_dir()

    def test_create_folder_in_subdirectory(self, tmp_shared_folder: Path) -> None:
        new_rel = create_folder(tmp_shared_folder, "subdir", "child")
        assert new_rel == "subdir/child"
        assert (tmp_shared_folder / "subdir" / "child").is_dir()

    def test_create_folder_already_exists_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(FileConflictError):
            create_folder(tmp_shared_folder, "", "subdir")

    def test_create_folder_invalid_name_empty_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            create_folder(tmp_shared_folder, "", "")

    def test_create_folder_invalid_name_slash_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            create_folder(tmp_shared_folder, "", "bad/folder")

    def test_create_folder_invalid_name_dotdot_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            create_folder(tmp_shared_folder, "", "..")

    def test_create_folder_invalid_name_null_byte_raises(
        self, tmp_shared_folder: Path
    ) -> None:
        with pytest.raises(InvalidFileNameError):
            create_folder(tmp_shared_folder, "", "bad\x00folder")

    def test_create_folder_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            create_folder(tmp_shared_folder, "../outside", "folder")


class TestDownloadAsZip:
    """Tests for download_as_zip service function."""

    def test_zip_single_file(self, tmp_shared_folder: Path) -> None:
        import zipfile
        from io import BytesIO as ZipBuf

        gen = download_as_zip(tmp_shared_folder, ["test.txt"])
        data = b"".join(gen)
        zf = zipfile.ZipFile(ZipBuf(data))
        assert "test.txt" in zf.namelist()
        assert zf.read("test.txt") == b"hello world"

    def test_zip_multiple_files(self, tmp_shared_folder: Path) -> None:
        import zipfile
        from io import BytesIO as ZipBuf

        gen = download_as_zip(tmp_shared_folder, ["test.txt", "subdir/nested.txt"])
        data = b"".join(gen)
        zf = zipfile.ZipFile(ZipBuf(data))
        names = zf.namelist()
        assert "test.txt" in names
        assert "subdir/nested.txt" in names

    def test_zip_directory(self, tmp_shared_folder: Path) -> None:
        import zipfile
        from io import BytesIO as ZipBuf

        gen = download_as_zip(tmp_shared_folder, ["subdir"])
        data = b"".join(gen)
        zf = zipfile.ZipFile(ZipBuf(data))
        # Should include nested file
        names = zf.namelist()
        matching = [n for n in names if "nested.txt" in n]
        assert len(matching) > 0

    def test_zip_traversal_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(PathTraversalError):
            # Consume the generator to trigger the error
            list(download_as_zip(tmp_shared_folder, ["../etc/passwd"]))

    def test_zip_nonexistent_raises(self, tmp_shared_folder: Path) -> None:
        with pytest.raises(FileNotFoundError):
            list(download_as_zip(tmp_shared_folder, ["nonexistent.txt"]))

    def test_zip_returns_generator(self, tmp_shared_folder: Path) -> None:
        """download_as_zip should return a generator (streaming), not bytes."""
        import collections.abc

        gen = download_as_zip(tmp_shared_folder, ["test.txt"])
        assert isinstance(gen, collections.abc.Generator)
