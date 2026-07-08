"""Tests for receive mode: only upload, server-info, and auth endpoints accessible."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_upload_works_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, POST /api/files/upload returns 200 (upload works)."""
    response = await async_client_receive.post(
        "/api/files/upload",
        files={"files": ("upload_receive_test.txt", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_server_info_works_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/server-info returns 200."""
    response = await async_client_receive.get("/api/server-info")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_get_files_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/files returns 403."""
    response = await async_client_receive.get("/api/files")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_download_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/files/download returns 403."""
    response = await async_client_receive.get(
        "/api/files/download",
        params={"path": "test.txt"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_snippet_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, POST /api/clipboard/ returns 403."""
    response = await async_client_receive.post(
        "/api/clipboard/",
        json={"title": "test"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_list_snippets_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/clipboard/ returns 403."""
    response = await async_client_receive.get("/api/clipboard/")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_list_file_requests_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/file-requests/ returns 403."""
    response = await async_client_receive.get("/api/file-requests/")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_share_management_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """Share-link management endpoints return 403 in receive mode."""
    create = await async_client_receive.post(
        "/api/shares",
        json={"file_path": "test.txt", "ttl": 3600},
    )
    listing = await async_client_receive.get("/api/shares")
    revoke = await async_client_receive.delete("/api/shares/fake-token")

    assert create.status_code == 403
    assert listing.status_code == 403
    assert revoke.status_code == 403


@pytest.mark.anyio
async def test_search_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/files/search returns 403."""
    response = await async_client_receive.get(
        "/api/files/search",
        params={"q": "test"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_preview_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, GET /api/files/preview returns 403."""
    response = await async_client_receive.get(
        "/api/files/preview",
        params={"path": "test.txt"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_download_zip_blocked_in_receive_mode(
    async_client_receive: AsyncClient,
) -> None:
    """In receive mode, POST /api/files/download-zip returns 403."""
    response = await async_client_receive.post(
        "/api/files/download-zip",
        json={"paths": ["test.txt"]},
    )
    assert response.status_code == 403
