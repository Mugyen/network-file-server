"""REST endpoints for clipboard snippet CRUD."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from server.app.models.enums import WSMessageType
from server.app.models.schemas import (
    CreateSnippetRequest,
    Snippet,
    UpdateSnippetTitleRequest,
)
from server.app.services.clipboard_service import get_clipboard_service
from server.app.services.connection_manager import manager

router = APIRouter(prefix="/api/clipboard", tags=["clipboard"])


@router.get("/", response_model=list[Snippet])
async def list_snippets() -> list[Snippet]:
    """Return all clipboard snippets."""
    service = get_clipboard_service()
    return await service.list_snippets()


@router.post("/", response_model=Snippet, status_code=201)
async def create_snippet(request: CreateSnippetRequest) -> Snippet:
    """Create a new snippet and broadcast to all connected devices."""
    service = get_clipboard_service()
    try:
        snippet = await service.create_snippet(request.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_CREATED.value,
        "snippet": snippet.model_dump(),
    })
    return snippet


@router.patch("/{snippet_id}", response_model=Snippet)
async def update_snippet_title(
    snippet_id: str,
    request: UpdateSnippetTitleRequest,
) -> Snippet:
    """Update snippet title and broadcast to all connected devices."""
    service = get_clipboard_service()
    try:
        snippet = await service.update_title(snippet_id, request.title)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_UPDATED.value,
        "snippet": snippet.model_dump(),
    })
    return snippet


@router.delete("/{snippet_id}")
async def delete_snippet(snippet_id: str) -> dict:
    """Delete a snippet and broadcast deletion to all connected devices."""
    service = get_clipboard_service()
    try:
        await service.delete_snippet(snippet_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await manager.broadcast_all({
        "type": WSMessageType.SNIPPET_DELETED.value,
        "snippet_id": snippet_id,
    })
    return {"status": "deleted"}
