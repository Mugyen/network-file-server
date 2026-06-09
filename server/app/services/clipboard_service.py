"""Clipboard snippet CRUD with SQLite persistence."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.app.models.schemas import Snippet
from server.app.services.sqlite_store import ClipboardRow, get_state_store

MAX_SNIPPETS = 50
MAX_CONTENT_LENGTH = 10000


class ClipboardService:
    """Manages clipboard snippets persisted in SQLite."""

    def __init__(self, data_dir: Path) -> None:
        self._store = get_state_store(data_dir)

    async def list_snippets(self) -> list[Snippet]:
        """Return all snippets sorted by created_at ascending."""
        rows = self._store.list_clipboard_snippets()
        return [Snippet(**row.__dict__) for row in rows]

    async def create_snippet(self, title: str) -> Snippet:
        """Create a new snippet with the given title and empty content.

        Raises ValueError if snippet count exceeds MAX_SNIPPETS.
        """
        if self._store.count_clipboard_snippets() >= MAX_SNIPPETS:
            raise ValueError(f"Maximum snippet count ({MAX_SNIPPETS}) exceeded")
        now = datetime.now(timezone.utc).isoformat()
        row = ClipboardRow(
            id=uuid.uuid4().hex[:12],
            title=title,
            content="",
            created_at=now,
            updated_at=now,
        )
        self._store.insert_clipboard_snippet(row)
        return Snippet(**row.__dict__)

    async def update_snippet(self, snippet_id: str, content: str) -> Snippet:
        """Update snippet content. Raises KeyError if not found, ValueError if content too long."""
        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Content exceeds maximum length ({MAX_CONTENT_LENGTH} characters)"
            )
        row = self._store.update_clipboard_snippet(snippet_id, content=content)
        return Snippet(**row.__dict__)

    async def update_title(self, snippet_id: str, title: str) -> Snippet:
        """Update snippet title. Raises KeyError if not found."""
        row = self._store.update_clipboard_snippet(snippet_id, title=title)
        return Snippet(**row.__dict__)

    async def delete_snippet(self, snippet_id: str) -> None:
        """Delete a snippet. Raises KeyError if not found."""
        self._store.delete_clipboard_snippet(snippet_id)
