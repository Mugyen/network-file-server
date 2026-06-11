"""Share link router for creating, listing, revoking, and serving share links.

Provides API endpoints for managing share links and HTML pages for
share link recipients to view/download shared files without the React SPA.
"""

import os
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature

from server.app.config import ServerConfig
from server.app.dependencies import get_config, get_share_service
from server.app.models.schemas import CreateShareRequest, ShareLinkInfo
from server.app.services.file_service import format_file_size, resolve_safe_path
from server.app.services.share_service import (
    ShareLinkExpiredError,
    ShareLinkRevokedError,
    ShareLinkService,
)
from shared.paths import repo_root

router = APIRouter()

# Resolve templates directory relative to repository root
_TEMPLATES_DIR = repo_root() / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.post("/api/shares", status_code=201, response_model=ShareLinkInfo)
async def create_share_link(
    request: Request,
    body: CreateShareRequest,
    config: ServerConfig = Depends(get_config),
    service: ShareLinkService = Depends(get_share_service),
) -> ShareLinkInfo:
    """Create a new share link for a file.

    Validates that the file exists in the shared folder before creating the link.
    Returns 404 if the file does not exist.
    """
    # Raises FileNotFoundError (-> 404 centrally) if the file is gone.
    resolve_safe_path(config.shared_folder, body.file_path)

    # create_link returns the full record — no reaching into internals.
    record = await service.create_link(body.file_path, body.ttl)
    file_name = Path(body.file_path).name
    created_at = record.created_at.isoformat()
    expires_at = (record.created_at + timedelta(seconds=record.ttl_seconds)).isoformat()
    share_url = f"{request.base_url}share/{record.token}"

    return ShareLinkInfo(
        token=record.token,
        file_path=body.file_path,
        file_name=file_name,
        created_at=created_at,
        expires_at=expires_at,
        ttl_seconds=record.ttl_seconds,
        share_url=share_url,
    )


@router.get("/api/shares", response_model=list[ShareLinkInfo])
async def list_share_links(
    request: Request,
    service: ShareLinkService = Depends(get_share_service),
) -> list[ShareLinkInfo]:
    """List all active (non-expired) share links."""
    records = await service.list_active_links()
    result: list[ShareLinkInfo] = []
    for record in records:
        file_name = Path(record.file_path).name
        created_at = record.created_at.isoformat()
        expires_at = (record.created_at + timedelta(seconds=record.ttl_seconds)).isoformat()
        share_url = f"{request.base_url}share/{record.token}"
        result.append(ShareLinkInfo(
            token=record.token,
            file_path=record.file_path,
            file_name=file_name,
            created_at=created_at,
            expires_at=expires_at,
            ttl_seconds=record.ttl_seconds,
            share_url=share_url,
        ))
    return result


@router.delete("/api/shares/{token}", status_code=204)
async def revoke_share_link(
    token: str,
    service: ShareLinkService = Depends(get_share_service),
) -> Response:
    """Revoke a share link by token.

    Raises ShareLinkNotFoundError (-> 404 centrally) for unknown tokens.
    """
    await service.revoke_link(token)
    return Response(status_code=204)


@router.get("/share/{token}", response_class=HTMLResponse)
async def share_page(
    request: Request,
    token: str,
    config: ServerConfig = Depends(get_config),
    service: ShareLinkService = Depends(get_share_service),
) -> Response:
    """Render the share download page for a valid token.

    Shows expired page for expired/revoked tokens.
    Shows unavailable page if the file was deleted after link creation.
    """
    try:
        file_path = await service.validate_token(token)
    except (ShareLinkExpiredError, ShareLinkRevokedError):
        return templates.TemplateResponse(request, "share_expired.html")
    except BadSignature:
        return templates.TemplateResponse(request, "share_expired.html")

    try:
        resolved = resolve_safe_path(config.shared_folder, file_path)
    except FileNotFoundError:
        return templates.TemplateResponse(request, "share_unavailable.html")

    file_name = resolved.name
    file_size = format_file_size(os.path.getsize(resolved))

    return templates.TemplateResponse(
        request,
        "share_download.html",
        {"file_name": file_name, "file_size": file_size, "token": token},
    )


@router.get("/share/{token}/download")
async def share_download(
    request: Request,
    token: str,
    config: ServerConfig = Depends(get_config),
    service: ShareLinkService = Depends(get_share_service),
) -> Response:
    """Serve the actual file for download via a share link token.

    Returns expired page for expired/revoked tokens.
    """
    try:
        file_path = await service.validate_token(token)
    except (ShareLinkExpiredError, ShareLinkRevokedError):
        return templates.TemplateResponse(request, "share_expired.html")
    except BadSignature:
        return templates.TemplateResponse(request, "share_expired.html")

    try:
        resolved = resolve_safe_path(config.shared_folder, file_path)
    except FileNotFoundError:
        return templates.TemplateResponse(request, "share_unavailable.html")

    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )
