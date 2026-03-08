"""File service module -- stub for TDD RED phase."""

from pathlib import Path

from server.app.models.schemas import DirectoryListing


def format_file_size(size_bytes: int) -> str:
    raise NotImplementedError("format_file_size not yet implemented")


def resolve_safe_path(base_dir: Path, user_path: str) -> Path:
    raise NotImplementedError("resolve_safe_path not yet implemented")


def list_directory(base_dir: Path, relative_path: str) -> DirectoryListing:
    raise NotImplementedError("list_directory not yet implemented")
