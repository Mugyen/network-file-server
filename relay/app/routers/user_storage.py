"""Per-user relay storage API — /me/files/* (login required, quota-enforced).

Reuses the server file_service helpers (path-traversal-safe) with the
user's isolated directory as the base, so storage logic is not
re-implemented.
"""

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from server import (
    ConflictResolution,
    DeleteRequest,
    FileConflictError,
    PathTraversalError,
    delete_paths,
    download_file,
    list_directory,
    upload_file,
)

from relay.app.dependencies import get_current_identity, get_relay_state
from relay.app.services.session import SessionIdentity
from relay.app.services.user_storage import (
    quota_bytes,
    usage_bytes,
    user_dir,
)

router = APIRouter(prefix="/me", tags=["user-storage"])


@router.get("/quota")
async def get_quota(
    request: Request,
    identity: SessionIdentity = Depends(get_current_identity),
) -> dict[str, int]:
    state = get_relay_state(request)
    data_dir = Path(state.config.data_dir)
    # usage_bytes walks the whole user dir — keep it off the event loop.
    return {
        "usage": await asyncio.to_thread(usage_bytes, data_dir, identity.user_id),
        "quota": await quota_bytes(
            state.require_account_store(),
            state.config.default_user_quota_bytes,
            identity.user_id,
        ),
    }


@router.get("/files")
async def list_files(
    request: Request,
    path: str = "",
    identity: SessionIdentity = Depends(get_current_identity),
) -> Any:
    state = get_relay_state(request)
    base = user_dir(Path(state.config.data_dir), identity.user_id)
    try:
        listing = await asyncio.to_thread(list_directory, base, path)
        return listing.model_dump()
    except PathTraversalError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
    except FileNotFoundError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})


@router.post("/files/upload", response_model=None)
async def upload(
    files: list[UploadFile],
    request: Request,
    path: str = "",
    conflict_resolution: ConflictResolution | None = None,
    identity: SessionIdentity = Depends(get_current_identity),
) -> Any:
    state = get_relay_state(request)
    data_dir = Path(state.config.data_dir)
    base = user_dir(data_dir, identity.user_id)

    # Pre-check using the request size against remaining quota (the
    # Content-Length slightly over-counts via multipart overhead, which
    # is conservative — fine for a quota guard).
    quota = await quota_bytes(
        state.require_account_store(),
        state.config.default_user_quota_bytes,
        identity.user_id,
    )
    current = await asyncio.to_thread(usage_bytes, data_dir, identity.user_id)
    declared = int(request.headers.get("content-length", "0"))
    if declared and current + declared > quota:
        return JSONResponse(
            status_code=413,
            content={"error": "Storage quota exceeded", "quota": quota,
                     "usage": current},
        )

    written: list[str] = []
    try:
        results = []
        for f in files:
            result = await upload_file(base, path, f, conflict_resolution)
            results.append(result.model_dump())
            written.append(result.name)
    except PathTraversalError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
    except FileConflictError as exc:
        return JSONResponse(status_code=409, content={"error": str(exc)})

    # Post-write safety net (no/under-reported Content-Length): if the
    # write pushed the user over quota, roll back what we just wrote.
    if await asyncio.to_thread(usage_bytes, data_dir, identity.user_id) > quota:
        await asyncio.to_thread(
            delete_paths,
            base,
            [f"{path}/{n}".lstrip("/") if path else n for n in written],
        )
        return JSONResponse(
            status_code=413,
            content={"error": "Storage quota exceeded", "quota": quota},
        )
    return results


@router.get("/files/download", response_model=None)
async def download(
    request: Request,
    path: str,
    identity: SessionIdentity = Depends(get_current_identity),
) -> Any:
    state = get_relay_state(request)
    base = user_dir(Path(state.config.data_dir), identity.user_id)
    try:
        fp = download_file(base, path)
    except PathTraversalError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    return FileResponse(
        path=str(fp), filename=fp.name, media_type="application/octet-stream"
    )


@router.delete("/files", response_model=None)
async def delete(
    request: Request,
    body: DeleteRequest,
    identity: SessionIdentity = Depends(get_current_identity),
) -> Any:
    state = get_relay_state(request)
    base = user_dir(Path(state.config.data_dir), identity.user_id)
    try:
        deleted = await asyncio.to_thread(delete_paths, base, body.paths)
    except PathTraversalError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
    except FileNotFoundError as exc:
        return JSONResponse(status_code=404, content={"error": str(exc)})
    return {"deleted": deleted}
