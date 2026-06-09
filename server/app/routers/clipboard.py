"""REST endpoints for clipboard snippet CRUD."""


from fastapi import APIRouter, Depends, HTTPException

from server.app.dependencies import get_clipboard_service, get_connection_manager
from server.app.middleware.mode_guard import require_full_access, require_write_access
from server.app.services.clipboard_service import ClipboardService
from server.app.services.connection_manager import ConnectionManager

from server.app.models.enums import WSMessageType
from server.app.models.schemas import (
    CreateSnippetRequest,
    Snippet,
    UpdateSnippetTitleRequest,
)

router = APIRouter(prefix="/api/clipboard", tags=["clipboard"])


@router.get("/", response_model=list[Snippet], dependencies=[Depends(require_full_access)])
async def list_snippets(
    service: ClipboardService = Depends(get_clipboard_service),
) -> list[Snippet]:
    """Return all clipboard snippets."""
    return await service.list_snippets()


@router.post("/", response_model=Snippet, status_code=201, dependencies=[Depends(require_write_access), Depends(require_full_access)])
async def create_snippet(
    request: CreateSnippetRequest,
    service: ClipboardService = Depends(get_clipboard_service),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> Snippet:
    """Create a new snippet and broadcast to all connected devices."""
    try:
        snippet = await service.create_snippet(request.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_CREATED.value,
        "snippet": snippet.model_dump(),
    })
    return snippet


@router.patch("/{snippet_id}", response_model=Snippet, dependencies=[Depends(require_write_access), Depends(require_full_access)])
async def update_snippet_title(
    snippet_id: str,
    request: UpdateSnippetTitleRequest,
    service: ClipboardService = Depends(get_clipboard_service),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> Snippet:
    """Update snippet title and broadcast to all connected devices."""
    try:
        snippet = await service.update_title(snippet_id, request.title)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_UPDATED.value,
        "snippet": snippet.model_dump(),
    })
    return snippet


@router.delete("/{snippet_id}", dependencies=[Depends(require_write_access), Depends(require_full_access)])
async def delete_snippet(
    snippet_id: str,
    service: ClipboardService = Depends(get_clipboard_service),
    manager: ConnectionManager = Depends(get_connection_manager),
) -> dict:
    """Delete a snippet and broadcast deletion to all connected devices."""
    try:
        await service.delete_snippet(snippet_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_DELETED.value,
        "snippet_id": snippet_id,
    })
    return {"status": "deleted"}
