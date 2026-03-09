"""Clipboard snippet CRUD with JSON persistence."""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.app.models.schemas import Snippet
from server.app.services.persistence import read_json, write_json_atomic

MAX_SNIPPETS = 50
MAX_CONTENT_LENGTH = 10000


class ClipboardService:
    """Manages clipboard snippets with in-memory cache and JSON file persistence.

    Thread-safe via asyncio.Lock for concurrent read-modify-write operations.
    """

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path: Path = data_dir / "clipboard.json"
        self._lock: asyncio.Lock = asyncio.Lock()
        self._snippets: dict[str, dict] = {}
        self._loaded: bool = False

    async def _ensure_loaded(self) -> None:
        """Load snippets from file if not yet loaded."""
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            data = await read_json(self._file_path)
            self._snippets = data.get("snippets", {})
            self._loaded = True

    async def list_snippets(self) -> list[Snippet]:
        """Return all snippets sorted by created_at ascending."""
        await self._ensure_loaded()
        sorted_items = sorted(
            self._snippets.values(),
            key=lambda s: s["created_at"],
        )
        return [Snippet(**s) for s in sorted_items]

    async def create_snippet(self, title: str) -> Snippet:
        """Create a new snippet with the given title and empty content.

        Raises ValueError if snippet count exceeds MAX_SNIPPETS.
        """
        await self._ensure_loaded()
        if len(self._snippets) >= MAX_SNIPPETS:
            raise ValueError(f"Maximum snippet count ({MAX_SNIPPETS}) exceeded")
        now = datetime.now(timezone.utc).isoformat()
        snippet_id = uuid.uuid4().hex[:12]
        snippet_data = {
            "id": snippet_id,
            "title": title,
            "content": "",
            "created_at": now,
            "updated_at": now,
        }
        self._snippets[snippet_id] = snippet_data
        await self._persist()
        return Snippet(**snippet_data)

    async def update_snippet(self, snippet_id: str, content: str) -> Snippet:
        """Update snippet content. Raises KeyError if not found, ValueError if content too long."""
        await self._ensure_loaded()
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Content exceeds maximum length ({MAX_CONTENT_LENGTH} characters)"
            )
        if snippet_id not in self._snippets:
            raise KeyError(f"Snippet '{snippet_id}' not found")
        self._snippets[snippet_id]["content"] = content
        self._snippets[snippet_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._persist()
        return Snippet(**self._snippets[snippet_id])

    async def update_title(self, snippet_id: str, title: str) -> Snippet:
        """Update snippet title. Raises KeyError if not found."""
        await self._ensure_loaded()
        if snippet_id not in self._snippets:
            raise KeyError(f"Snippet '{snippet_id}' not found")
        self._snippets[snippet_id]["title"] = title
        self._snippets[snippet_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._persist()
        return Snippet(**self._snippets[snippet_id])

    async def delete_snippet(self, snippet_id: str) -> None:
        """Delete a snippet. Raises KeyError if not found."""
        await self._ensure_loaded()
        if snippet_id not in self._snippets:
            raise KeyError(f"Snippet '{snippet_id}' not found")
        del self._snippets[snippet_id]
        await self._persist()

    async def _persist(self) -> None:
        """Persist current snippets to disk atomically."""
        async with self._lock:
            await write_json_atomic(self._file_path, {"snippets": self._snippets})


_clipboard_service: ClipboardService | None = None


def get_clipboard_service() -> ClipboardService:
    """Lazily create and return the singleton ClipboardService.

    Uses shared_folder's parent / '.wfs_data' as the data directory.
    """
    global _clipboard_service
    if _clipboard_service is not None:
        return _clipboard_service
    from server.app.config import get_server_config

    config = get_server_config()
    data_dir = config.shared_folder.parent / ".wfs_data"
    _clipboard_service = ClipboardService(data_dir)
    return _clipboard_service
