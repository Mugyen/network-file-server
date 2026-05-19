"""Per-file uploader index — backs the RECEIVE role ("see own uploads").

A small JSON sidecar in the shared folder maps a file's relative path to
the username that uploaded it (via the trusted relay identity). RECEIVE
users only see/download files they themselves uploaded; untracked /
pre-existing files are invisible to them.
"""

from pathlib import Path

from server.app.services.persistence import read_json, write_json_atomic

_INDEX_NAME = ".wfs_upload_index.json"


def index_filename() -> str:
    """Name of the sidecar file (hidden from listings by callers)."""
    return _INDEX_NAME


def _index_path(shared_folder: Path) -> Path:
    return shared_folder / _INDEX_NAME


def _norm(rel_path: str) -> str:
    if not isinstance(rel_path, str) or len(rel_path.strip()) == 0:
        raise ValueError("rel_path must be a non-empty string")
    return rel_path.strip().lstrip("/")


async def record_upload(shared_folder: Path, rel_path: str, uploader: str) -> None:
    """Record that ``uploader`` uploaded the file at ``rel_path``."""
    if not isinstance(uploader, str) or len(uploader) == 0:
        raise ValueError("uploader must be a non-empty string")
    key = _norm(rel_path)
    path = _index_path(shared_folder)
    data = await read_json(path)
    data[key] = uploader
    await write_json_atomic(path, data)


async def is_owned_by(shared_folder: Path, rel_path: str, uploader: str) -> bool:
    """True if ``uploader`` is the recorded uploader of ``rel_path``."""
    data = await read_json(_index_path(shared_folder))
    return data.get(_norm(rel_path)) == uploader


async def owned_paths(shared_folder: Path, uploader: str) -> set[str]:
    """Return the set of relative paths uploaded by ``uploader``."""
    data = await read_json(_index_path(shared_folder))
    return {k for k, v in data.items() if v == uploader}
