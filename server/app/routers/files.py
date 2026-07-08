"""Files API router.

Provides endpoints for listing, uploading, downloading, renaming,
deleting files, creating folders, batch ZIP download, search, and preview.

Error handling: routes raise domain exceptions (server/app/exceptions.py);
the central handlers registered in server/app/error_handlers.py map them to
HTTP responses. Routes never construct error responses themselves.
"""

import asyncio
import mimetypes
from typing import Any
from urllib.parse import quote

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from server.app.models.enums import ConflictResolution
from server.app.models.schemas import (
    CreateFolderRequest,
    DeleteRequest,
    DirectoryListing,
    DownloadZipRequest,
    RenameRequest,
    SearchResult,
    UploadResult,
)
from server.app.middleware.mode_guard import (
    receive_scope_user,
    require_browse_access,
    require_full_access,
    require_write_access,
)
from server.app.services import upload_index
from server.app.services.relay_identity import trusted_user
from server.app.models.enums import ToastType
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


@router.get("/files", response_model=DirectoryListing, dependencies=[Depends(require_browse_access)])
async def get_files(request: Request, path: str = Query("")) -> dict:
    """List files in the shared folder with optional TTL expiry data.

    Query parameter 'path' specifies a relative subdirectory.
    Empty string means root of the shared folder.
    Enriches each file entry with expires_at (ISO timestamp or null).
    """
    config = request.app.state.config
    # Offloaded: iterdir+stat block, and this loop also carries tunnel
    # traffic when the agent runs the server in-process.
    listing = await asyncio.to_thread(list_directory, config.shared_folder, path)
    result = listing.model_dump()

    # RECEIVE role: show only files this user uploaded (hide
    # directories and everyone else's / pre-existing files).
    scope_user = receive_scope_user(request)
    if scope_user is not None:
        owned = await upload_index.owned_paths(request.app.state.store, scope_user)
        filtered = []
        for e in result["entries"]:
            if e.get("type") == "directory":
                continue
            name = e.get("name", "")
            key = f"{path}/{name}".lstrip("/") if path else name
            if key in owned:
                filtered.append(e)
        result["entries"] = filtered

    # Enrich file entries with TTL expiry timestamps. The provider is
    # injected by whoever hosts this app in-process (relay drop box);
    # standalone mode has none and the feature is absent.
    ttl_provider = request.app.state.file_ttl_provider
    if config.mount_code is not None and ttl_provider is not None:
        ttl_records = await ttl_provider.get_ttl_for_mount(config.mount_code)
        ttl_map: dict[str, str] = {}
        for file_path, expires_at in ttl_records:
            ttl_map[file_path] = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        for entry in result.get("entries", []):
            # Build relative path from listing directory + filename
            name = entry.get("name", "")
            rel = f"{path}/{name}".lstrip("/") if path else name
            entry["expires_at"] = ttl_map.get(rel)
    else:
        # Standalone mode (no provider) or LAN serving — no TTLs.
        for entry in result.get("entries", []):
            entry["expires_at"] = None

    return result


@router.post("/files/upload", response_model=list[UploadResult], dependencies=[Depends(require_write_access)])
async def upload_files(
    files: list[UploadFile],
    request: Request,
    path: str = Query(""),
    conflict_resolution: ConflictResolution | None = Query(None),
    ttl: int | None = Query(None),
    x_device_id: str | None = Header(None),
    x_device_name: str | None = Header(None),
) -> Any:
    """Upload one or more files to the specified directory.

    Accepts multipart file upload. Optional conflict_resolution query param
    controls behavior when file already exists: overwrite, rename, or skip.
    Broadcasts toast to WebSocket clients after successful upload.
    """
    config = request.app.state.config
    results = []
    for file in files:
        result = await upload_file(
            config.shared_folder, path, file, conflict_resolution
        )
        results.append(result.model_dump())

    # Record the uploader (trusted relay identity) so RECEIVE users
    # can later see their own uploads.
    uploader = trusted_user(config, request.headers)
    if uploader is not None:
        for r in results:
            name = r.get("name", "")
            if name:
                rel = f"{path}/{name}".lstrip("/") if path else name
                await upload_index.record_upload(
                    request.app.state.store, rel, uploader
                )

    # Record file TTL for each uploaded file (when a provider is injected)
    effective_ttl = ttl if ttl is not None else 86400  # Default 1 day
    if effective_ttl > 0 and config.mount_code is not None:
        # None = standalone mode (no provider injected) — nothing to record.
        ttl_provider = request.app.state.file_ttl_provider
        if ttl_provider is not None:
            for r in results:
                # Build relative path from upload directory + filename
                name = r.get("name", "")
                if name:
                    file_path = f"{path}/{name}".lstrip("/") if path else name
                    await ttl_provider.record_file_ttl(config.mount_code, file_path, effective_ttl)

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
        await request.app.state.manager.broadcast(toast_msg, x_device_id)
    else:
        await request.app.state.manager.broadcast_all(toast_msg)

    return results


@router.get("/files/download", response_model=None, dependencies=[Depends(require_browse_access)])
async def download_single_file(request: Request, path: str = Query(...)) -> Any:
    """Download a single file as an attachment.

    Returns FileResponse with Content-Disposition: attachment.
    Uses filename*=UTF-8'' encoding for unicode support.
    """
    config = request.app.state.config
    scope_user = receive_scope_user(request)
    if scope_user is not None and not await upload_index.is_owned_by(
        request.app.state.store, path, scope_user
    ):
        raise FileNotFoundError("Not found")
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


@router.post("/files/download-zip", response_model=None, dependencies=[Depends(require_browse_access)])
async def download_zip(request: Request, body: DownloadZipRequest) -> Any:
    """Download multiple files as a streaming ZIP archive.

    Accepts a JSON body with paths list. Uses zipstream-ng for
    memory-efficient streaming without buffering the full archive.
    """
    config = request.app.state.config
    scope_user = receive_scope_user(request)
    if scope_user is not None:
        for path in body.paths:
            if not await upload_index.is_owned_by(
                request.app.state.store, path, scope_user
            ):
                raise FileNotFoundError("Not found")
    zip_generator = download_as_zip(config.shared_folder, body.paths)
    return StreamingResponse(
        zip_generator,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=download.zip"},
    )


@router.patch("/files/rename", response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def rename_file(http_request: Request, request: RenameRequest) -> Any:
    """Rename a file or directory.

    Accepts JSON body with path (original) and new_name.
    Returns the new relative path.
    """
    config = http_request.app.state.config
    new_path = rename_path(config.shared_folder, request.path, request.new_name)
    return {"path": new_path}


@router.delete("/files", response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def delete_files(http_request: Request, request: DeleteRequest) -> Any:
    """Delete one or more files or directories.

    Accepts JSON body with paths list.
    Returns the list of deleted paths.
    """
    config = http_request.app.state.config
    deleted = delete_paths(config.shared_folder, request.paths)
    return {"deleted": deleted}


@router.post("/folders", status_code=201, response_model=None, dependencies=[Depends(require_write_access), Depends(require_full_access)])
def create_new_folder(http_request: Request, request: CreateFolderRequest) -> Any:
    """Create a new folder.

    Accepts JSON body with parent_path and name.
    Returns the new folder's relative path.
    """
    config = http_request.app.state.config
    new_path = create_folder(
        config.shared_folder, request.parent_path, request.name
    )
    return {"path": new_path}


@router.get("/files/search", response_model=SearchResult, dependencies=[Depends(require_browse_access)])
def search_files_endpoint(  # sync on purpose: FastAPI runs `def` routes in its threadpool, keeping the rglob walk off the event loop
    request: Request,
    q: str = Query(...),
    path: str = Query(""),
) -> Any:
    """Search for files matching query recursively from path.

    Query parameter 'q' is the search term (required, non-empty).
    Query parameter 'path' is the starting directory (default: root).
    Returns SearchResult with matching FileEntry list.

    RECEIVE-scoped users get no search results (search results lack the
    full path needed to safely scope to own uploads).
    """
    config = request.app.state.config
    if receive_scope_user(request) is not None:
        return SearchResult(query=q, path=path, entries=[]).model_dump()
    results = search_files(config.shared_folder, path, q)
    return SearchResult(query=q, path=path, entries=results).model_dump()


@router.get("/files/preview", response_model=None, dependencies=[Depends(require_browse_access)])
async def preview_file(
    request: Request,
    path: str = Query(...),
) -> Any:
    """Serve a file inline for preview.

    Returns FileResponse with Content-Disposition: inline and
    correct Content-Type from mimetypes. Starlette FileResponse
    handles Range requests (206 Partial Content) automatically.
    """
    config = request.app.state.config
    scope_user = receive_scope_user(request)
    if scope_user is not None and not await upload_index.is_owned_by(
        request.app.state.store, path, scope_user
    ):
        raise FileNotFoundError("Not found")
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
