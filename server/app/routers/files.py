"""Files API router.

Provides endpoints for listing, uploading, downloading, renaming,
deleting files, creating folders, batch ZIP download, search, and preview.
"""

import mimetypes
from typing import Any
from urllib.parse import quote

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from server.app.config import get_server_config
from server.app.exceptions import (
    FileConflictError,
    InvalidFileNameError,
    PathTraversalError,
)
from server.app.models.enums import ConflictResolution
from server.app.models.schemas import (
    CreateFolderRequest,
    DeleteRequest,
    DownloadZipRequest,
    RenameRequest,
    SearchResult,
)
from server.app.middleware.mode_guard import require_full_access, require_write_access
from server.app.models.enums import ToastType
from server.app.services.connection_manager import manager
from server.app.services.file_service import (
    create_folder,
    delete_paths,
    download_as_zip,
    download_file,
    list_directory,
    rename_path,
    search_files,
    upload_file,
)

router = APIRouter(prefix="/api", tags=["files"])


def _handle_path_traversal(exc: PathTraversalError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": str(exc)})


def _handle_not_found(exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": str(exc)})


def _handle_conflict(exc: FileConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": str(exc),
            "path": exc.path,
            "existing_path": exc.existing_path,
        },
    )


def _handle_invalid_name(exc: InvalidFileNameError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "name": exc.name, "reason": exc.reason},
    )


@router.get("/files", dependencies=[Depends(require_full_access)])
def get_files(path: str = Query("")) -> dict:
    """List files in the shared folder.

    Query parameter 'path' specifies a relative subdirectory.
    Empty string means root of the shared folder.
    """
    config = get_server_config()
    try:
        listing = list_directory(config.shared_folder, path)
        return listing.model_dump()
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)  # type: ignore[return-value]
    except FileNotFoundError as exc:
        return _handle_not_found(exc)  # type: ignore[return-value]


@router.post("/files/upload", response_model=None, dependencies=[Depends(require_write_access)])
async def upload_files(
    files: list[UploadFile],
    path: str = Query(""),
    conflict_resolution: ConflictResolution | None = Query(None),
    x_device_id: str | None = Header(None),
    x_device_name: str | None = Header(None),
) -> Any:
    """Upload one or more files to the specified directory.

    Accepts multipart file upload. Optional conflict_resolution query param
    controls behavior when file already exists: overwrite, rename, or skip.
    Broadcasts toast to WebSocket clients after successful upload.
    """
    config = get_server_config()
    try:
        results = []
        for file in files:
            result = await upload_file(
                config.shared_folder, path, file, conflict_resolution
            )
            results.append(result.model_dump())

        # Broadcast upload toast to WS clients
        file_count = len(results)
        uploader_name = x_device_name if x_device_name is not None else "Someone"
        file_word = "file" if file_count == 1 else "files"
        toast_msg = {
            "type": "toast",
            "toast_type": ToastType.FILE_UPLOADED.value,
            "message": f"{file_count} {file_word} uploaded by {uploader_name}",
            "device_name": uploader_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if x_device_id is not None:
            await manager.broadcast(toast_msg, x_device_id)
        else:
            await manager.broadcast_all(toast_msg)

        return results
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except FileConflictError as exc:
        return _handle_conflict(exc)


@router.get("/files/download", response_model=None, dependencies=[Depends(require_full_access)])
def download_single_file(path: str = Query(...)) -> Any:
    """Download a single file as an attachment.

    Returns FileResponse with Content-Disposition: attachment.
    Uses filename*=UTF-8'' encoding for unicode support.
    """
    config = get_server_config()
    try:
        file_path = download_file(config.shared_folder, path)
        encoded_name = quote(file_path.name)
        return FileResponse(
            path=str(file_path),
            filename=file_path.name,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": (
                    f"attachment; filename*=UTF-8''{encoded_name}"
                )
            },
        )
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@router.post("/files/download-zip", response_model=None, dependencies=[Depends(require_full_access)])
def download_zip(request: DownloadZipRequest) -> Any:
    """Download multiple files as a streaming ZIP archive.

    Accepts a JSON body with paths list. Uses zipstream-ng for
    memory-efficient streaming without buffering the full archive.
    """
    config = get_server_config()
    try:
        zip_generator = download_as_zip(config.shared_folder, request.paths)
        return StreamingResponse(
            zip_generator,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=download.zip"},
        )
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)


@router.patch("/files/rename", response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def rename_file(request: RenameRequest) -> Any:
    """Rename a file or directory.

    Accepts JSON body with path (original) and new_name.
    Returns the new relative path.
    """
    config = get_server_config()
    try:
        new_path = rename_path(config.shared_folder, request.path, request.new_name)
        return {"path": new_path}
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except FileConflictError as exc:
        return _handle_conflict(exc)
    except InvalidFileNameError as exc:
        return _handle_invalid_name(exc)


@router.delete("/files", response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def delete_files(request: DeleteRequest) -> Any:
    """Delete one or more files or directories.

    Accepts JSON body with paths list.
    Returns the list of deleted paths.
    """
    config = get_server_config()
    try:
        deleted = delete_paths(config.shared_folder, request.paths)
        return {"deleted": deleted}
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)


@router.post("/folders", status_code=201, response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def create_new_folder(request: CreateFolderRequest) -> Any:
    """Create a new folder.

    Accepts JSON body with parent_path and name.
    Returns the new folder's relative path.
    """
    config = get_server_config()
    try:
        new_path = create_folder(
            config.shared_folder, request.parent_path, request.name
        )
        return {"path": new_path}
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except FileConflictError as exc:
        return _handle_conflict(exc)
    except InvalidFileNameError as exc:
        return _handle_invalid_name(exc)


@router.get("/files/search", response_model=None, dependencies=[Depends(require_full_access)])
def search_files_endpoint(
    q: str = Query(...),
    path: str = Query(""),
) -> Any:
    """Search for files matching query recursively from path.

    Query parameter 'q' is the search term (required, non-empty).
    Query parameter 'path' is the starting directory (default: root).
    Returns SearchResult with matching FileEntry list.
    """
    config = get_server_config()
    try:
        results = search_files(config.shared_folder, path, q)
        return SearchResult(query=q, path=path, entries=results).model_dump()
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@router.get("/files/preview", response_model=None, dependencies=[Depends(require_full_access)])
def preview_file(
    path: str = Query(...),
) -> Any:
    """Serve a file inline for preview.

    Returns FileResponse with Content-Disposition: inline and
    correct Content-Type from mimetypes. Starlette FileResponse
    handles Range requests (206 Partial Content) automatically.
    """
    config = get_server_config()
    try:
        file_path = download_file(config.shared_folder, path)
        mime_type, _ = mimetypes.guess_type(file_path.name)
        if mime_type is None:
            mime_type = "application/octet-stream"
        encoded_name = quote(file_path.name)
        return FileResponse(
            path=str(file_path),
            media_type=mime_type,
            headers={
                "Content-Disposition": (
                    f"inline; filename*=UTF-8''{encoded_name}"
                )
            },
        )
    except PathTraversalError as exc:
        return _handle_path_traversal(exc)
    except FileNotFoundError as exc:
        return _handle_not_found(exc)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
