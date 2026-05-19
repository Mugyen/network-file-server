"""File service module.

Provides path traversal protection, directory listing, and all file
management operations: upload, download, delete, rename, create folder,
and ZIP download.
"""

import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import aiofiles
from zipstream import ZipStream

from server.app.exceptions import (
    FileConflictError,
    InvalidFileNameError,
    PathTraversalError,
)
from server.app.models.enums import ConflictResolution, FileType
from server.app.models.schemas import DirectoryListing, FileEntry, UploadResult

UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB chunks


def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string.

    Uses units B, KB, MB, GB, TB with one decimal place.
    Reuses logic from the original network_file_server.py get_file_size().
    """
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def resolve_safe_path(base_dir: Path, user_path: str) -> Path:
    """Resolve a user-provided path relative to base_dir with safety checks.

    Validates that the resolved path stays within base_dir.
    Raises PathTraversalError for traversal attempts or symlinks escaping base.
    Raises FileNotFoundError if the resolved target does not exist.
    """
    base_resolved = base_dir.resolve()

    # Handle empty path as base directory itself
    if user_path == "":
        return base_resolved

    # Reject absolute paths immediately
    if user_path.startswith("/"):
        raise PathTraversalError(user_path)

    # Resolve the full path (follows symlinks)
    candidate = (base_resolved / user_path).resolve()

    # Check the resolved path is within base
    if not candidate.is_relative_to(base_resolved):
        raise PathTraversalError(user_path)

    # Check existence
    if not candidate.exists():
        raise FileNotFoundError(
            f"Path '{user_path}' does not exist in shared folder"
        )

    return candidate


def _resolve_safe_path_for_new(base_dir: Path, user_path: str) -> Path:
    """Resolve a user-provided path for a NEW target that does not yet exist.

    Same safety checks as resolve_safe_path but does NOT require existence.
    Used by upload and create_folder where the target is being created.
    """
    base_resolved = base_dir.resolve()

    if user_path == "":
        return base_resolved

    if user_path.startswith("/"):
        raise PathTraversalError(user_path)

    candidate = (base_resolved / user_path).resolve()

    if not candidate.is_relative_to(base_resolved):
        raise PathTraversalError(user_path)

    return candidate


def _validate_name(name: str) -> None:
    """Validate a file or folder name.

    Rejects empty names, names containing /, .., or null bytes.
    Raises InvalidFileNameError with descriptive reason on failure.
    """
    if name == "":
        raise InvalidFileNameError(name, "name must not be empty")
    if "/" in name:
        raise InvalidFileNameError(name, "name must not contain '/'")
    if name == "..":
        raise InvalidFileNameError(name, "name must not be '..'")
    if ".." in name.split(os.sep):
        raise InvalidFileNameError(name, "name must not contain '..'")
    if "\x00" in name:
        raise InvalidFileNameError(name, "name must not contain null bytes")


def list_directory(base_dir: Path, relative_path: str) -> DirectoryListing:
    """List the contents of a directory within the shared folder.

    Validates the path via resolve_safe_path first.
    Returns a DirectoryListing with FileEntry objects for each item.
    """
    target = resolve_safe_path(base_dir, relative_path)

    entries: list[FileEntry] = []
    for item in target.iterdir():
        item_stat = item.stat()
        is_dir = stat.S_ISDIR(item_stat.st_mode)
        file_type = FileType.DIRECTORY if is_dir else FileType.FILE
        mtime = datetime.fromtimestamp(item_stat.st_mtime, tz=timezone.utc)
        modified_iso = mtime.isoformat()

        entries.append(
            FileEntry(
                name=item.name,
                size=item_stat.st_size,
                size_display=format_file_size(item_stat.st_size),
                type=file_type,
                modified=modified_iso,
            )
        )

    return DirectoryListing(path=relative_path, entries=entries)


async def upload_file(
    base_dir: Path,
    relative_dir: str,
    upload: object,
    conflict_resolution: ConflictResolution | None,
) -> UploadResult:
    """Save an uploaded file to disk via aiofiles chunked write.

    Uses resolve_safe_path for the target directory.
    Handles conflict resolution: OVERWRITE writes via temp+replace,
    RENAME appends _1, _2 etc, SKIP returns with skipped=True.
    Raises FileConflictError when file exists and no resolution provided.
    Raises PathTraversalError for directory traversal attempts.
    """
    target_dir = resolve_safe_path(base_dir, relative_dir)

    filename: str = upload.filename  # type: ignore[attr-defined]
    destination = target_dir / filename

    # Check for conflict
    if destination.exists():
        if conflict_resolution is None:
            raise FileConflictError(filename, str(destination))

        if conflict_resolution == ConflictResolution.SKIP:
            existing_stat = destination.stat()
            return UploadResult(
                name=filename,
                size=existing_stat.st_size,
                size_display=format_file_size(existing_stat.st_size),
                skipped=True,
            )

        if conflict_resolution == ConflictResolution.RENAME:
            stem = destination.stem
            suffix = destination.suffix
            counter = 1
            while True:
                new_name = f"{stem}_{counter}{suffix}"
                candidate = target_dir / new_name
                if not candidate.exists():
                    destination = candidate
                    filename = new_name
                    break
                counter += 1

        # OVERWRITE: write to temp file then os.replace for atomicity

    # Write file to disk in chunks
    if conflict_resolution == ConflictResolution.OVERWRITE and (target_dir / upload.filename).exists():  # type: ignore[attr-defined]
        # Atomic overwrite: write to temp, then replace
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        bytes_written = await _write_upload_chunks(upload, temp_path)
        os.replace(temp_path, target_dir / upload.filename)  # type: ignore[attr-defined]
        destination = target_dir / upload.filename  # type: ignore[attr-defined]
        filename = upload.filename  # type: ignore[attr-defined]
    else:
        bytes_written = await _write_upload_chunks(upload, destination)

    return UploadResult(
        name=filename,
        size=bytes_written,
        size_display=format_file_size(bytes_written),
        skipped=False,
    )


async def _write_upload_chunks(upload: object, destination: Path) -> int:
    """Write upload data to destination in chunks. Returns total bytes written."""
    bytes_written = 0
    async with aiofiles.open(destination, "wb") as out_file:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_SIZE)  # type: ignore[attr-defined]
            if not chunk:
                break
            await out_file.write(chunk)
            bytes_written += len(chunk)
    return bytes_written


def search_files(base_dir: Path, search_root: str, query: str) -> list[FileEntry]:
    """Search for files matching query recursively from search_root.

    Walks the directory tree from search_root using rglob.
    Matches query (case-insensitive contains) against file/directory names.
    Returns FileEntry list with paths relative to search_root.

    Raises PathTraversalError if search_root resolves outside base_dir.
    Raises ValueError if query is an empty string.
    """
    if query == "":
        raise ValueError("Search query must not be empty")

    base_resolved = base_dir.resolve()
    root_resolved = resolve_safe_path(base_dir, search_root)

    query_lower = query.lower()
    results: list[FileEntry] = []

    for item in root_resolved.rglob("*"):
        # Skip items that are not regular files or directories (e.g., broken symlinks)
        if not item.is_file() and not item.is_dir():
            continue

        # Prevent symlink escape: ensure item is still within base_dir
        try:
            item_resolved = item.resolve()
            if not item_resolved.is_relative_to(base_resolved):
                continue
        except OSError:
            continue

        if query_lower not in item.name.lower():
            continue

        item_stat = item.stat()
        is_dir = stat.S_ISDIR(item_stat.st_mode)
        file_type = FileType.DIRECTORY if is_dir else FileType.FILE
        mtime = datetime.fromtimestamp(item_stat.st_mtime, tz=timezone.utc)
        modified_iso = mtime.isoformat()

        # Build relative path from search_root (not base_dir)
        relative_name = str(item.relative_to(root_resolved))

        results.append(
            FileEntry(
                name=relative_name,
                size=item_stat.st_size,
                size_display=format_file_size(item_stat.st_size),
                type=file_type,
                modified=modified_iso,
            )
        )

    return results


def download_file(base_dir: Path, relative_path: str) -> Path:
    """Validate and return the resolved Path for a downloadable file.

    Raises ValueError if the path points to a directory.
    Raises PathTraversalError for traversal attempts.
    Raises FileNotFoundError if file does not exist.
    """
    resolved = resolve_safe_path(base_dir, relative_path)

    if resolved.is_dir():
        raise ValueError(
            f"Path '{relative_path}' is a directory, not a downloadable file"
        )

    return resolved


def delete_paths(base_dir: Path, paths: list[str]) -> list[str]:
    """Delete one or more paths within the shared folder.

    Uses os.remove for files and shutil.rmtree for directories.
    Raises PathTraversalError for any invalid path.
    Raises FileNotFoundError for missing paths.
    Returns the list of deleted paths.
    """
    deleted: list[str] = []
    for path_str in paths:
        resolved = resolve_safe_path(base_dir, path_str)
        if resolved.is_dir():
            shutil.rmtree(resolved)
        else:
            os.remove(resolved)
        deleted.append(path_str)
    return deleted


def rename_path(base_dir: Path, old_relative: str, new_name: str) -> str:
    """Rename a file or directory within the shared folder.

    Validates the new name, checks for conflicts at the target location.
    Returns the new relative path from base_dir.
    Raises InvalidFileNameError for invalid names.
    Raises FileConflictError if target name already exists.
    Raises PathTraversalError for traversal attempts.
    """
    _validate_name(new_name)

    resolved = resolve_safe_path(base_dir, old_relative)
    new_path = resolved.parent / new_name

    if new_path.exists():
        raise FileConflictError(
            new_name,
            str(new_path.relative_to(base_dir.resolve())),
        )

    resolved.rename(new_path)

    # Compute the relative path from base_dir for the return value
    base_resolved = base_dir.resolve()
    return str(new_path.relative_to(base_resolved))


def create_folder(base_dir: Path, parent_relative: str, folder_name: str) -> str:
    """Create a new directory within the shared folder.

    Validates the folder name and checks for conflicts.
    Returns the new relative path from base_dir.
    Raises InvalidFileNameError for invalid names.
    Raises FileConflictError if folder already exists.
    Raises PathTraversalError for traversal attempts.
    """
    _validate_name(folder_name)

    parent = resolve_safe_path(base_dir, parent_relative)
    new_dir = parent / folder_name

    if new_dir.exists():
        raise FileConflictError(
            folder_name,
            str(new_dir.relative_to(base_dir.resolve())),
        )

    new_dir.mkdir(parents=False)

    base_resolved = base_dir.resolve()
    return str(new_dir.relative_to(base_resolved))


def download_as_zip(
    base_dir: Path, paths: list[str]
) -> Generator[bytes, None, None]:
    """Create a streaming ZIP archive from the given paths.

    Uses zipstream-ng for memory-efficient streaming.
    Validates all paths via resolve_safe_path EAGERLY before returning
    the generator, so errors surface before streaming starts.
    Returns a generator yielding ZIP chunks for StreamingResponse.
    Raises PathTraversalError for traversal attempts.
    Raises FileNotFoundError for missing paths.
    """
    base_resolved = base_dir.resolve()
    resolved_paths: list[Path] = []

    # Validate all paths up front so errors surface before streaming starts
    # This runs eagerly (not lazily) because it's in the outer function
    for path_str in paths:
        resolved = resolve_safe_path(base_dir, path_str)
        resolved_paths.append(resolved)

    return _zip_stream(base_resolved, resolved_paths)


def _zip_stream(
    base_resolved: Path, resolved_paths: list[Path]
) -> Generator[bytes, None, None]:
    """Inner generator that yields ZIP chunks. Paths are pre-validated."""
    zs = ZipStream()
    for resolved in resolved_paths:
        arcname = str(resolved.relative_to(base_resolved))
        zs.add_path(resolved, arcname=arcname)

    yield from zs
