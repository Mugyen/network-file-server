"""Tests for read-only mode: all write endpoints return 403, reads still work."""

import io

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.mark.anyio
async def test_upload_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """POST /api/files/upload returns 403 in read-only mode."""
    response = await async_client_read_only.post(
        "/api/files/upload",
        files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_rename_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """PATCH /api/files/rename returns 403 in read-only mode."""
    response = await async_client_read_only.patch(
        "/api/files/rename",
        json={"path": "test.txt", "new_name": "renamed.txt"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_delete_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """DELETE /api/files returns 403 in read-only mode."""
    response = await async_client_read_only.request(
        "DELETE",
        "/api/files",
        json={"paths": ["test.txt"]},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_folder_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """POST /api/folders returns 403 in read-only mode."""
    response = await async_client_read_only.post(
        "/api/folders",
        json={"parent_path": "", "name": "newfolder"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_snippet_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """POST /api/clipboard/ returns 403 in read-only mode."""
    response = await async_client_read_only.post(
        "/api/clipboard/",
        json={"title": "test"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_update_snippet_title_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """PATCH /api/clipboard/{id} returns 403 in read-only mode."""
    response = await async_client_read_only.patch(
        "/api/clipboard/fake-id",
        json={"title": "new title"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_delete_snippet_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """DELETE /api/clipboard/{id} returns 403 in read-only mode."""
    response = await async_client_read_only.delete("/api/clipboard/fake-id")
    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_file_request_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """POST /api/file-requests/ returns 403 in read-only mode."""
    response = await async_client_read_only.post(
        "/api/file-requests/",
        json={"description": "need a file"},
        headers={"x-device-id": "dev1", "x-device-name": "Device 1"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_fulfill_file_request_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """POST /api/file-requests/{id}/fulfill returns 403 in read-only mode."""
    response = await async_client_read_only.post(
        "/api/file-requests/fake-id/fulfill",
        files={"file": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        headers={"x-device-name": "Device 1"},
    )
    assert response.status_code == 403


@pytest.mark.anyio
async def test_dismiss_file_request_blocked_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """DELETE /api/file-requests/{id} returns 403 in read-only mode."""
    response = await async_client_read_only.delete(
        "/api/file-requests/fake-id",
        headers={"x-device-id": "dev1"},
    )
    assert response.status_code == 403


def test_websocket_snippet_update_ignored_in_read_only(
    configured_app_read_only: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """WebSocket snippet_update message is ignored in read-only mode."""
    client = TestClient(configured_app_read_only)
    with client.websocket_connect("/ws?device_name=test") as ws:
        # Send a snippet_update -- should be silently ignored in read-only
        ws.send_json({
            "type": "snippet_update",
            "snippet_id": "fake-id",
            "content": "new content",
        })
        # Send ping to verify connection still works
        ws.send_json({"type": "ping"})
        # Read messages until pong (skip broadcast messages)
        found_pong = False
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "pong":
                found_pong = True
                break
            # Should NOT see snippet_updated broadcast
            assert msg.get("type") != "snippet_updated"
        assert found_pong


@pytest.mark.anyio
async def test_get_files_works_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """GET /api/files (read) still works in read-only mode."""
    response = await async_client_read_only.get("/api/files")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_download_works_in_read_only(
    async_client_read_only: AsyncClient,
) -> None:
    """GET /api/files/download still works in read-only mode."""
    response = await async_client_read_only.get(
        "/api/files/download",
        params={"path": "test.txt"},
    )
    assert response.status_code == 200
