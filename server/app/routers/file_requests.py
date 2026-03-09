"""File requests API router.

Provides endpoints for creating, listing, fulfilling, and dismissing file requests.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Header, UploadFile
from fastapi.responses import JSONResponse

from server.app.config import get_server_config
from server.app.models.enums import RequestStatus, ToastType, WSMessageType
from server.app.models.schemas import CreateFileRequestPayload, FileRequest
from server.app.services.connection_manager import manager
from server.app.services.file_request_service import get_file_request_service
from server.app.services.file_service import upload_file

router = APIRouter(prefix="/api/file-requests", tags=["file-requests"])


@router.get("/")
async def list_file_requests() -> list[FileRequest]:
    """Return all non-dismissed file requests."""
    service = get_file_request_service()
    return await service.list_requests()


@router.post("/", status_code=201)
async def create_file_request(
    payload: CreateFileRequestPayload,
    x_device_id: str = Header(...),
    x_device_name: str = Header(...),
) -> FileRequest:
    """Create a new file request and broadcast to other devices."""
    service = get_file_request_service()
    request = await service.create_request(
        payload.description, x_device_id, x_device_name
    )

    # Broadcast request_created to all OTHER connections
    ws_msg = {
        "type": WSMessageType.REQUEST_CREATED.value,
        "request": request.model_dump(),
    }
    await manager.broadcast(ws_msg, x_device_id)

    # Toast to all other connections
    toast_msg = {
        "type": "toast",
        "toast_type": ToastType.REQUEST_CREATED.value,
        "message": f"{x_device_name} is requesting: {request.description}",
        "device_name": x_device_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast(toast_msg, x_device_id)

    return request


@router.post("/{request_id}/fulfill")
async def fulfill_file_request(
    request_id: str,
    file: UploadFile,
    x_device_name: str = Header(...),
) -> FileRequest:
    """Fulfill a file request by uploading a file."""
    service = get_file_request_service()
    config = get_server_config()

    # Upload the file to the shared folder root
    upload_result = await upload_file(config.shared_folder, "", file, None)

    # Mark the request as fulfilled
    fulfilled = await service.fulfill_request(
        request_id, x_device_name, upload_result.name, upload_result.name
    )

    # Broadcast request_fulfilled to ALL connections
    ws_msg = {
        "type": WSMessageType.REQUEST_FULFILLED.value,
        "request": fulfilled.model_dump(),
    }
    await manager.broadcast_all(ws_msg)

    # Send targeted toast to the requester
    toast_msg = {
        "type": "toast",
        "toast_type": ToastType.REQUEST_FULFILLED.value,
        "message": f"{x_device_name} fulfilled your request with {upload_result.name}",
        "device_name": x_device_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await manager.send_to(fulfilled.requester_device_id, toast_msg)
    except KeyError:
        pass  # Requester disconnected -- no toast

    return fulfilled


@router.delete("/{request_id}")
async def dismiss_file_request(
    request_id: str,
    x_device_id: str = Header(...),
) -> dict:
    """Dismiss a file request. Only the requester can dismiss."""
    service = get_file_request_service()
    await service.dismiss_request(request_id, x_device_id)

    # Broadcast request_dismissed to all connections
    ws_msg = {
        "type": WSMessageType.REQUEST_DISMISSED.value,
        "request_id": request_id,
    }
    await manager.broadcast_all(ws_msg)

    return {"status": "dismissed"}
