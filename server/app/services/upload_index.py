"""Per-file uploader index for RECEIVE role ownership checks.

Mappings live in SQLite alongside the other server-side state so they
survive restarts without leaving storage artifacts inside the shared folder.
"""

from pathlib import Path

from server.app.services.sqlite_store import get_state_store


def _norm(rel_path: str) -> str:
    if not isinstance(rel_path, str) or len(rel_path.strip()) == 0:
        raise ValueError("rel_path must be a non-empty string")
    return rel_path.strip().lstrip("/")


async def record_upload(shared_folder: Path, rel_path: str, uploader: str) -> None:
    """Record that ``uploader`` uploaded the file at ``rel_path``."""
    if not isinstance(uploader, str) or len(uploader) == 0:
        raise ValueError("uploader must be a non-empty string")
    key = _norm(rel_path)
    store = get_state_store(shared_folder.parent / ".wfs_data")
    store.record_upload_owner(key, uploader)


async def is_owned_by(shared_folder: Path, rel_path: str, uploader: str) -> bool:
    """True if ``uploader`` is the recorded uploader of ``rel_path``."""
    store = get_state_store(shared_folder.parent / ".wfs_data")
    return store.is_upload_owned_by(_norm(rel_path), uploader)


async def owned_paths(shared_folder: Path, uploader: str) -> set[str]:
    """Return the set of relative paths uploaded by ``uploader``."""
    store = get_state_store(shared_folder.parent / ".wfs_data")
    return store.owned_upload_paths(uploader)
