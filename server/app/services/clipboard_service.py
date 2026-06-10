"""Clipboard snippet CRUD with SQLite persistence.

Store calls run via asyncio.to_thread so SQLite I/O never blocks the
event loop (the store is sync sqlite3 + RLock by design — see
sqlite_store.py).
"""

import asyncio
import uuid
from datetime import datetime, timezone

from server.app.exceptions import SnippetNotFoundError, SnippetValidationError
from server.app.models.schemas import Snippet
from server.app.services.sqlite_store import ClipboardRow, ServerStateStore

MAX_SNIPPETS = 50
MAX_CONTENT_LENGTH = 10000


class ClipboardService:
    """Manages clipboard snippets persisted in SQLite.

    Raises domain exceptions (SnippetNotFoundError, SnippetValidationError);
    the store's generic KeyError never escapes this service.
    """

    def __init__(self, store: ServerStateStore) -> None:
        if not isinstance(store, ServerStateStore):
            raise ValueError(f"store must be a ServerStateStore, got {type(store)!r}")
        self._store = store

    async def list_snippets(self) -> list[Snippet]:
        """Return all snippets sorted by created_at ascending."""
        rows = await asyncio.to_thread(self._store.list_clipboard_snippets)
        return [Snippet(**row.__dict__) for row in rows]

    async def create_snippet(self, title: str) -> Snippet:
        """Create a new snippet with the given title and empty content.

        Raises SnippetValidationError if snippet count exceeds MAX_SNIPPETS.
        """
        if await asyncio.to_thread(self._store.count_clipboard_snippets) >= MAX_SNIPPETS:
            raise SnippetValidationError(
                f"Maximum snippet count ({MAX_SNIPPETS}) exceeded"
            )
        now = datetime.now(timezone.utc).isoformat()
        row = ClipboardRow(
            id=uuid.uuid4().hex[:12],
            title=title,
            content="",
            created_at=now,
            updated_at=now,
        )
        await asyncio.to_thread(self._store.insert_clipboard_snippet, row)
        return Snippet(**row.__dict__)

    async def update_snippet(self, snippet_id: str, content: str) -> Snippet:
        """Update snippet content.

        Raises SnippetNotFoundError if the id does not exist and
        SnippetValidationError if the content is too long.
        """
        if len(content) > MAX_CONTENT_LENGTH:
            raise SnippetValidationError(
                f"Content exceeds maximum length ({MAX_CONTENT_LENGTH} characters)"
            )
        try:
            row = await asyncio.to_thread(
                self._store.update_clipboard_snippet, snippet_id, content=content
            )
        except KeyError as exc:
            # Store speaks KeyError; translate to the domain exception.
            raise SnippetNotFoundError(snippet_id) from exc
        return Snippet(**row.__dict__)

    async def update_title(self, snippet_id: str, title: str) -> Snippet:
        """Update snippet title. Raises SnippetNotFoundError if not found."""
        try:
            row = await asyncio.to_thread(
                self._store.update_clipboard_snippet, snippet_id, title=title
            )
        except KeyError as exc:
            # Store speaks KeyError; translate to the domain exception.
            raise SnippetNotFoundError(snippet_id) from exc
        return Snippet(**row.__dict__)

    async def delete_snippet(self, snippet_id: str) -> None:
        """Delete a snippet. Raises SnippetNotFoundError if not found."""
        try:
            await asyncio.to_thread(self._store.delete_clipboard_snippet, snippet_id)
        except KeyError as exc:
            # Store speaks KeyError; translate to the domain exception.
            raise SnippetNotFoundError(snippet_id) from exc
