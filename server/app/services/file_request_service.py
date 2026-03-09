"""File request service with JSON persistence.

Allows devices to request specific files, and other devices to fulfill them.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from server.app.models.enums import RequestStatus
from server.app.models.schemas import FileRequest
from server.app.services.persistence import read_json, write_json_atomic


class FileRequestService:
    """CRUD service for file requests with atomic JSON persistence."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._file_path = data_dir / "file_requests.json"
        self._lock = asyncio.Lock()
        self._requests: dict[str, dict] | None = None
        data_dir.mkdir(parents=True, exist_ok=True)

    async def _ensure_loaded(self) -> None:
        """Load requests from disk if not yet cached."""
        if self._requests is None:
            data = await read_json(self._file_path)
            self._requests = data.get("requests", {})

    async def list_requests(self) -> list[FileRequest]:
        """Return all non-dismissed requests, newest first."""
        await self._ensure_loaded()
        assert self._requests is not None
        results = [
            FileRequest(**v)
            for v in self._requests.values()
            if v["status"] != RequestStatus.DISMISSED.value
        ]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results

    async def create_request(
        self,
        description: str,
        requester_device_id: str,
        requester_device_name: str,
    ) -> FileRequest:
        """Create a new file request. Raises ValueError if description is empty."""
        if not description.strip():
            raise ValueError("description must not be empty")

        await self._ensure_loaded()
        assert self._requests is not None

        request_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        entry: dict = {
            "id": request_id,
            "description": description.strip(),
            "requester_device_id": requester_device_id,
            "requester_device_name": requester_device_name,
            "status": RequestStatus.PENDING.value,
            "created_at": now,
            "fulfilled_by_device_name": None,
            "fulfilled_file_name": None,
            "fulfilled_file_path": None,
            "fulfilled_at": None,
        }
        self._requests[request_id] = entry
        await self._persist()
        return FileRequest(**entry)

    async def fulfill_request(
        self,
        request_id: str,
        fulfilled_by_device_name: str,
        file_name: str,
        file_path: str,
    ) -> FileRequest:
        """Mark a request as fulfilled. Raises KeyError if not found, ValueError if not PENDING."""
        await self._ensure_loaded()
        assert self._requests is not None

        if request_id not in self._requests:
            raise KeyError(f"File request '{request_id}' not found")

        entry = self._requests[request_id]
        if entry["status"] != RequestStatus.PENDING.value:
            raise ValueError(f"Can only fulfill PENDING requests, got {entry['status']}")

        now = datetime.now(timezone.utc).isoformat()
        entry["status"] = RequestStatus.FULFILLED.value
        entry["fulfilled_by_device_name"] = fulfilled_by_device_name
        entry["fulfilled_file_name"] = file_name
        entry["fulfilled_file_path"] = file_path
        entry["fulfilled_at"] = now
        await self._persist()
        return FileRequest(**entry)

    async def dismiss_request(self, request_id: str, caller_device_id: str) -> None:
        """Dismiss a request. Only the requester may dismiss. Raises KeyError/ValueError."""
        await self._ensure_loaded()
        assert self._requests is not None

        if request_id not in self._requests:
            raise KeyError(f"File request '{request_id}' not found")

        entry = self._requests[request_id]
        if entry["requester_device_id"] != caller_device_id:
            raise ValueError("Only the requester can dismiss their request")

        entry["status"] = RequestStatus.DISMISSED.value
        await self._persist()

    async def _persist(self) -> None:
        """Write current state to disk atomically."""
        async with self._lock:
            assert self._requests is not None
            await write_json_atomic(self._file_path, {"requests": self._requests})


_service_instance: FileRequestService | None = None


def get_file_request_service() -> FileRequestService:
    """Return the singleton FileRequestService instance."""
    global _service_instance
    if _service_instance is None:
        from server.app.config import get_server_config
        data_dir = get_server_config().shared_folder.parent / ".wfs_data"
        _service_instance = FileRequestService(data_dir)
    return _service_instance
