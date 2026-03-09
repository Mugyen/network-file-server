"""Tests for FileRequestService and file-requests REST endpoints."""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.app.models.enums import RequestStatus
from server.app.services.file_request_service import FileRequestService


# --- Service unit tests ---


@pytest_asyncio.fixture
async def service(tmp_path: Path) -> FileRequestService:
    return FileRequestService(tmp_path / "data")


@pytest.mark.asyncio
async def test_list_requests_empty(service: FileRequestService) -> None:
    result = await service.list_requests()
    assert result == []


@pytest.mark.asyncio
async def test_create_request(service: FileRequestService) -> None:
    req = await service.create_request("Need meeting notes", "dev-1", "Swift Fox")
    assert req.description == "Need meeting notes"
    assert req.requester_device_id == "dev-1"
    assert req.requester_device_name == "Swift Fox"
    assert req.status == RequestStatus.PENDING
    assert req.fulfilled_by_device_name is None
    assert req.fulfilled_file_name is None
    assert req.fulfilled_file_path is None
    assert req.fulfilled_at is None
    assert len(req.id) > 0
    assert len(req.created_at) > 0


@pytest.mark.asyncio
async def test_create_request_empty_description_raises(service: FileRequestService) -> None:
    with pytest.raises(ValueError, match="description"):
        await service.create_request("", "dev-1", "Swift Fox")
    with pytest.raises(ValueError, match="description"):
        await service.create_request("   ", "dev-1", "Swift Fox")


@pytest.mark.asyncio
async def test_fulfill_request(service: FileRequestService) -> None:
    req = await service.create_request("Need slides", "dev-1", "Fox")
    fulfilled = await service.fulfill_request(req.id, "Bold Bear", "slides.pdf", "slides.pdf")
    assert fulfilled.status == RequestStatus.FULFILLED
    assert fulfilled.fulfilled_by_device_name == "Bold Bear"
    assert fulfilled.fulfilled_file_name == "slides.pdf"
    assert fulfilled.fulfilled_file_path == "slides.pdf"
    assert fulfilled.fulfilled_at is not None


@pytest.mark.asyncio
async def test_fulfill_nonexistent_raises(service: FileRequestService) -> None:
    with pytest.raises(KeyError):
        await service.fulfill_request("nonexistent-id", "Bear", "f.txt", "f.txt")


@pytest.mark.asyncio
async def test_fulfill_non_pending_raises(service: FileRequestService) -> None:
    req = await service.create_request("Need file", "dev-1", "Fox")
    await service.fulfill_request(req.id, "Bear", "f.txt", "f.txt")
    with pytest.raises(ValueError, match="PENDING"):
        await service.fulfill_request(req.id, "Bear", "g.txt", "g.txt")


@pytest.mark.asyncio
async def test_dismiss_request(service: FileRequestService) -> None:
    req = await service.create_request("Need file", "dev-1", "Fox")
    await service.dismiss_request(req.id, "dev-1")
    # Dismissed requests should not appear in list
    result = await service.list_requests()
    assert len(result) == 0


@pytest.mark.asyncio
async def test_dismiss_nonexistent_raises(service: FileRequestService) -> None:
    with pytest.raises(KeyError):
        await service.dismiss_request("nonexistent-id", "dev-1")


@pytest.mark.asyncio
async def test_dismiss_by_non_requester_raises(service: FileRequestService) -> None:
    req = await service.create_request("Need file", "dev-1", "Fox")
    with pytest.raises(ValueError, match="requester"):
        await service.dismiss_request(req.id, "dev-other")


@pytest.mark.asyncio
async def test_persistence_survives_reinstantiation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    svc1 = FileRequestService(data_dir)
    req = await svc1.create_request("Persist me", "dev-1", "Fox")

    # New instance from same directory
    svc2 = FileRequestService(data_dir)
    result = await svc2.list_requests()
    assert len(result) == 1
    assert result[0].id == req.id
    assert result[0].description == "Persist me"


@pytest.mark.asyncio
async def test_list_excludes_dismissed(service: FileRequestService) -> None:
    req1 = await service.create_request("Keep me", "dev-1", "Fox")
    req2 = await service.create_request("Dismiss me", "dev-1", "Fox")
    await service.dismiss_request(req2.id, "dev-1")
    result = await service.list_requests()
    assert len(result) == 1
    assert result[0].id == req1.id


# --- REST endpoint tests ---


@pytest_asyncio.fixture
async def client(tmp_path: Path) -> AsyncClient:
    """Create test client with isolated data dir."""
    from server.app.config import set_server_config, ServerConfig

    shared = tmp_path / "shared"
    shared.mkdir()
    set_server_config(ServerConfig(shared_folder=shared, port=8000))

    # Patch the service factory to use tmp_path -- also reset the module singleton
    import server.app.services.file_request_service as frs_mod
    import server.app.routers.file_requests as fr_router_mod
    original_factory = frs_mod.get_file_request_service
    test_service = FileRequestService(tmp_path / "frs_data")
    patched_factory = lambda: test_service  # type: ignore[assignment]  # noqa: E731
    frs_mod.get_file_request_service = patched_factory  # type: ignore[assignment]
    fr_router_mod.get_file_request_service = patched_factory  # type: ignore[assignment]

    from server.app.main import create_app
    app = create_app()
    # Remove SPA catch-all that interferes with test routing
    app.routes[:] = [r for r in app.routes if not (hasattr(r, "path") and getattr(r, "path", "") == "/{path:path}")]
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    frs_mod.get_file_request_service = original_factory
    fr_router_mod.get_file_request_service = original_factory


@pytest.mark.asyncio
async def test_rest_list_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/file-requests/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_rest_create_request(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/file-requests/",
        json={"description": "Need notes"},
        headers={"X-Device-Id": "dev-1", "X-Device-Name": "Fox"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "Need notes"
    assert data["status"] == "pending"
    assert data["requester_device_id"] == "dev-1"


@pytest.mark.asyncio
async def test_rest_fulfill_request(client: AsyncClient, tmp_path: Path) -> None:
    # Create request first
    resp = await client.post(
        "/api/file-requests/",
        json={"description": "Need file"},
        headers={"X-Device-Id": "dev-1", "X-Device-Name": "Fox"},
    )
    request_id = resp.json()["id"]

    # Fulfill with file upload
    resp = await client.post(
        f"/api/file-requests/{request_id}/fulfill",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers={"X-Device-Name": "Bear"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fulfilled"
    assert data["fulfilled_by_device_name"] == "Bear"
    assert data["fulfilled_file_name"] == "test.txt"


@pytest.mark.asyncio
async def test_rest_dismiss_request(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/file-requests/",
        json={"description": "Dismiss me"},
        headers={"X-Device-Id": "dev-1", "X-Device-Name": "Fox"},
    )
    request_id = resp.json()["id"]

    resp = await client.delete(
        f"/api/file-requests/{request_id}",
        headers={"X-Device-Id": "dev-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"

    # Verify it's gone from list
    resp = await client.get("/api/file-requests/")
    assert resp.json() == []
