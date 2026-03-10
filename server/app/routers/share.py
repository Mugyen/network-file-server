"""Share link router for creating, listing, revoking, and serving share links.

Provides API endpoints for managing share links and HTML pages for
share link recipients to view/download shared files without the React SPA.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature

from server.app.config import get_server_config
from server.app.models.enums import ShareTTL
from server.app.models.schemas import CreateShareRequest, ShareLinkInfo
from server.app.services.file_service import format_file_size, resolve_safe_path
from server.app.services.share_service import (
    ShareLinkExpiredError,
    ShareLinkNotFoundError,
    ShareLinkRevokedError,
    get_share_service,
)

router = APIRouter()

# Resolve templates directory relative to project root
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.post("/api/shares", status_code=201, response_model=ShareLinkInfo)
async def create_share_link(request: Request, body: CreateShareRequest) -> ShareLinkInfo:
    """Create a new share link for a file.

    Validates that the file exists in the shared folder before creating the link.
    Returns 404 if the file does not exist.
    """
    config = get_server_config()
    try:
        resolve_safe_path(config.shared_folder, body.file_path)
    except FileNotFoundError:
        return Response(  # type: ignore[return-value]
            content='{"detail":"File not found"}',
            status_code=404,
            media_type="application/json",
        )

    service = get_share_service()
    token = service.create_link(body.file_path, body.ttl)

    record = service._active_links[token]
    file_name = Path(body.file_path).name
    created_at = record.created_at.isoformat()
    expires_at = (record.created_at + timedelta(seconds=record.ttl_seconds)).isoformat()
    share_url = f"{request.base_url}share/{token}"

    return ShareLinkInfo(
        token=token,
        file_path=body.file_path,
        file_name=file_name,
        created_at=created_at,
        expires_at=expires_at,
        ttl_seconds=record.ttl_seconds,
        share_url=share_url,
    )


@router.get("/api/shares", response_model=list[ShareLinkInfo])
async def list_share_links(request: Request) -> list[ShareLinkInfo]:
    """List all active (non-expired) share links."""
    service = get_share_service()
    records = service.list_active_links()
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
async def revoke_share_link(token: str) -> Response:
    """Revoke a share link by token. Returns 404 if not found."""
    service = get_share_service()
    try:
        service.revoke_link(token)
    except ShareLinkNotFoundError:
        return Response(
            content='{"detail":"Share link not found"}',
            status_code=404,
            media_type="application/json",
        )
    return Response(status_code=204)


@router.get("/share/{token}", response_class=HTMLResponse)
async def share_page(request: Request, token: str) -> Response:
    """Render the share download page for a valid token.

    Shows expired page for expired/revoked tokens.
    Shows unavailable page if the file was deleted after link creation.
    """
    service = get_share_service()
    try:
        file_path = service.validate_token(token)
    except (ShareLinkExpiredError, ShareLinkRevokedError):
        return templates.TemplateResponse(request, "share_expired.html")
    except BadSignature:
        return templates.TemplateResponse(request, "share_expired.html")

    config = get_server_config()
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
async def share_download(request: Request, token: str) -> Response:
    """Serve the actual file for download via a share link token.

    Returns expired page for expired/revoked tokens.
    """
    service = get_share_service()
    try:
        file_path = service.validate_token(token)
    except (ShareLinkExpiredError, ShareLinkRevokedError):
        return templates.TemplateResponse(request, "share_expired.html")
    except BadSignature:
        return templates.TemplateResponse(request, "share_expired.html")

    config = get_server_config()
    try:
        resolved = resolve_safe_path(config.shared_folder, file_path)
    except FileNotFoundError:
        return templates.TemplateResponse(request, "share_unavailable.html")

    return FileResponse(
        path=str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )
