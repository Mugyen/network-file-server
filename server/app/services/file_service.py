"""File service module.

Provides path traversal protection and directory listing functionality.
"""

import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from server.app.exceptions import PathTraversalError
from server.app.models.enums import FileType
from server.app.models.schemas import DirectoryListing, FileEntry


def format_file_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string.

    Uses units B, KB, MB, GB, TB with one decimal place.
    Reuses logic from the original wifi_file_server.py get_file_size().
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
