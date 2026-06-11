"""Tests for the central domain-exception -> HTTP mapping (error_handlers.py).

A minimal app with one route per exception verifies each mapping's status
code and response shape without involving real services.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from server.app.error_handlers import register_exception_handlers
from server.app.exceptions import (
    AccessDeniedError,
    FileConflictError,
    InvalidFileNameError,
    InvalidFileRequestError,
    PathTraversalError,
    ReadOnlyError,
    SnippetNotFoundError,
    SnippetValidationError,
)
from server.app.services.share_service import ShareLinkNotFoundError

_CASES: list[tuple[Exception, int]] = [
    (PathTraversalError("../etc"), 403),
    (FileNotFoundError("gone.txt"), 404),
    (FileConflictError("a.txt", "b.txt"), 409),
    (InvalidFileNameError("x/y", "slash"), 400),
    (InvalidFileRequestError("bad request"), 400),
    (ReadOnlyError("upload"), 403),
    (AccessDeniedError("nope"), 403),
    (ShareLinkNotFoundError("tok"), 404),
    (SnippetNotFoundError("snip"), 404),
    (SnippetValidationError("too long"), 400),
]


def _app_raising(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return app


@pytest.mark.anyio
@pytest.mark.parametrize("exc,status", _CASES, ids=[type(e).__name__ for e, _ in _CASES])
async def test_exception_maps_to_status(exc: Exception, status: int) -> None:
    """Each domain exception maps to its documented status with a detail body."""
    transport = ASGITransport(app=_app_raising(exc))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    assert resp.status_code == status
    assert "detail" in resp.json()


@pytest.mark.anyio
async def test_conflict_carries_paths() -> None:
    """FileConflictError responses expose path and existing_path fields."""
    transport = ASGITransport(app=_app_raising(FileConflictError("new.txt", "old.txt")))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    body = resp.json()
    assert body["path"] == "new.txt"
    assert body["existing_path"] == "old.txt"


@pytest.mark.anyio
async def test_invalid_name_carries_reason() -> None:
    """InvalidFileNameError responses expose name and reason fields."""
    transport = ASGITransport(app=_app_raising(InvalidFileNameError("a/b", "slash")))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    body = resp.json()
    assert body["name"] == "a/b"
    assert body["reason"] == "slash"


def test_register_rejects_non_app() -> None:
    """register_exception_handlers validates its input."""
    with pytest.raises(ValueError):
        register_exception_handlers("not an app")  # type: ignore[arg-type]
