"""Per-file uploader index for RECEIVE role ownership checks.

Mappings live in SQLite alongside the other server-side state so they
survive restarts without leaving storage artifacts inside the shared folder.

Callers pass the app's store (``request.app.state.store``); this module
holds no state of its own. Store calls run via asyncio.to_thread so the
event loop never blocks on SQLite I/O.
"""

import asyncio

from server.app.services.sqlite_store import ServerStateStore


def _norm(rel_path: str) -> str:
    if not isinstance(rel_path, str) or len(rel_path.strip()) == 0:
        raise ValueError("rel_path must be a non-empty string")
    return rel_path.strip().lstrip("/")


async def record_upload(store: ServerStateStore, rel_path: str, uploader: str) -> None:
    """Record that ``uploader`` uploaded the file at ``rel_path``."""
    if not isinstance(uploader, str) or len(uploader) == 0:
        raise ValueError("uploader must be a non-empty string")
    await asyncio.to_thread(store.record_upload_owner, _norm(rel_path), uploader)


async def is_owned_by(store: ServerStateStore, rel_path: str, uploader: str) -> bool:
    """True if ``uploader`` is the recorded uploader of ``rel_path``."""
    return await asyncio.to_thread(store.is_upload_owned_by, _norm(rel_path), uploader)


async def owned_paths(store: ServerStateStore, uploader: str) -> set[str]:
    """Return the set of relative paths uploaded by ``uploader``."""
    return await asyncio.to_thread(store.owned_upload_paths, uploader)
