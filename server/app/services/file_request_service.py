"""File request service with SQLite persistence.

Allows devices to request specific files, and other devices to fulfill them.
Store calls run via asyncio.to_thread so SQLite I/O never blocks the event loop.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from server.app.models.enums import RequestStatus
from server.app.models.schemas import FileRequest
from server.app.services.sqlite_store import FileRequestRow, ServerStateStore


class FileRequestService:
    """CRUD service for file requests backed by SQLite."""

    def __init__(self, store: ServerStateStore) -> None:
        if not isinstance(store, ServerStateStore):
            raise ValueError(f"store must be a ServerStateStore, got {type(store)!r}")
        self._store = store

    async def list_requests(self) -> list[FileRequest]:
        """Return all non-dismissed requests, newest first."""
        rows = await asyncio.to_thread(self._store.list_file_requests)
        return [FileRequest(**row.__dict__) for row in rows]

    async def create_request(
        self,
        description: str,
        requester_device_id: str,
        requester_device_name: str,
    ) -> FileRequest:
        """Create a new file request. Raises ValueError if description is empty."""
        if not description.strip():
            raise ValueError("description must not be empty")

        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = FileRequestRow(
            id=request_id,
            description=description.strip(),
            requester_device_id=requester_device_id,
            requester_device_name=requester_device_name,
            status=RequestStatus.PENDING.value,
            created_at=now,
            fulfilled_by_device_name=None,
            fulfilled_file_name=None,
            fulfilled_file_path=None,
            fulfilled_at=None,
        )
        await asyncio.to_thread(self._store.insert_file_request, row)
        return FileRequest(**row.__dict__)

    async def fulfill_request(
        self,
        request_id: str,
        fulfilled_by_device_name: str,
        file_name: str,
        file_path: str,
    ) -> FileRequest:
        """Mark a request as fulfilled. Raises KeyError if not found, ValueError if not PENDING."""
        current = await asyncio.to_thread(self._store.get_file_request, request_id)
        if current.status != RequestStatus.PENDING.value:
            raise ValueError(f"Can only fulfill PENDING requests, got {current.status}")

        now = datetime.now(timezone.utc).isoformat()
        row = await asyncio.to_thread(
            self._store.update_file_request,
            request_id,
            status=RequestStatus.FULFILLED.value,
            fulfilled_by_device_name=fulfilled_by_device_name,
            fulfilled_file_name=file_name,
            fulfilled_file_path=file_path,
            fulfilled_at=now,
        )
        return FileRequest(**row.__dict__)

    async def dismiss_request(self, request_id: str, caller_device_id: str) -> None:
        """Dismiss a request. Only the requester may dismiss. Raises KeyError/ValueError."""
        entry = await asyncio.to_thread(self._store.get_file_request, request_id)
        if entry.requester_device_id != caller_device_id:
            raise ValueError("Only the requester can dismiss their request")
        await asyncio.to_thread(self._store.dismiss_file_request, request_id)
