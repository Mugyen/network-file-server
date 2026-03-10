"""Tests for ClipboardService CRUD, persistence, and REST endpoints."""

from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.app.services.clipboard_service import ClipboardService


# --- ClipboardService unit tests ---


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """Provide a temporary data directory for clipboard storage."""
    return tmp_path / "wfs_data"


@pytest_asyncio.fixture()
async def service(data_dir: Path) -> ClipboardService:
    """Provide a fresh ClipboardService instance."""
    return ClipboardService(data_dir)


class TestListSnippets:
    @pytest.mark.asyncio()
    async def test_empty_list(self, service: ClipboardService) -> None:
        result = await service.list_snippets()
        assert result == []


class TestCreateSnippet:
    @pytest.mark.asyncio()
    async def test_creates_with_fields(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Test Note")
        assert snippet.title == "Test Note"
        assert snippet.content == ""
        assert len(snippet.id) == 12
        assert snippet.created_at != ""
        assert snippet.updated_at != ""

    @pytest.mark.asyncio()
    async def test_max_limit_raises(self, service: ClipboardService) -> None:
        for i in range(50):
            await service.create_snippet(f"Note {i}")
        with pytest.raises(ValueError, match="Maximum snippet count"):
            await service.create_snippet("One too many")


class TestUpdateSnippet:
    @pytest.mark.asyncio()
    async def test_updates_content(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Note")
        updated = await service.update_snippet(snippet.id, "Hello world")
        assert updated.content == "Hello world"
        assert updated.updated_at >= snippet.updated_at

    @pytest.mark.asyncio()
    async def test_nonexistent_raises(self, service: ClipboardService) -> None:
        with pytest.raises(KeyError, match="not found"):
            await service.update_snippet("nonexistent", "content")

    @pytest.mark.asyncio()
    async def test_max_content_length(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Note")
        with pytest.raises(ValueError, match="maximum length"):
            await service.update_snippet(snippet.id, "x" * 10001)

    @pytest.mark.asyncio()
    async def test_exact_max_content_ok(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Note")
        updated = await service.update_snippet(snippet.id, "x" * 10000)
        assert len(updated.content) == 10000


class TestUpdateTitle:
    @pytest.mark.asyncio()
    async def test_updates_title(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Old Title")
        updated = await service.update_title(snippet.id, "New Title")
        assert updated.title == "New Title"

    @pytest.mark.asyncio()
    async def test_nonexistent_raises(self, service: ClipboardService) -> None:
        with pytest.raises(KeyError, match="not found"):
            await service.update_title("nonexistent", "title")


class TestDeleteSnippet:
    @pytest.mark.asyncio()
    async def test_deletes(self, service: ClipboardService) -> None:
        snippet = await service.create_snippet("Note")
        await service.delete_snippet(snippet.id)
        result = await service.list_snippets()
        assert len(result) == 0

    @pytest.mark.asyncio()
    async def test_nonexistent_raises(self, service: ClipboardService) -> None:
        with pytest.raises(KeyError, match="not found"):
            await service.delete_snippet("nonexistent")


class TestPersistence:
    @pytest.mark.asyncio()
    async def test_survives_reinstantiation(self, data_dir: Path) -> None:
        svc1 = ClipboardService(data_dir)
        await svc1.create_snippet("Persistent Note")
        await svc1.update_snippet(
            (await svc1.list_snippets())[0].id, "Some content"
        )

        # New instance loads from the same file
        svc2 = ClipboardService(data_dir)
        snippets = await svc2.list_snippets()
        assert len(snippets) == 1
        assert snippets[0].title == "Persistent Note"
        assert snippets[0].content == "Some content"


# --- REST endpoint tests ---


@pytest_asyncio.fixture()
async def client(data_dir: Path) -> AsyncClient:
    """Create an httpx AsyncClient wired to the FastAPI app with test config."""
    from server.app.config import create_default_config, set_server_config

    # Create a valid shared folder for ServerConfig
    shared_folder = data_dir.parent / "shared"
    shared_folder.mkdir(parents=True, exist_ok=True)
    set_server_config(create_default_config(shared_folder=shared_folder, port=8000))

    # Reset the clipboard service singleton to use our test data_dir
    import server.app.services.clipboard_service as cs_module
    cs_module._clipboard_service = ClipboardService(data_dir)

    from server.app.main import create_app
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup singleton
    cs_module._clipboard_service = None


class TestRESTEndpoints:
    @pytest.mark.asyncio()
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/clipboard/")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio()
    async def test_create_and_list(self, client: AsyncClient) -> None:
        resp = await client.post("/api/clipboard/", json={"title": "My Note"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "My Note"
        assert data["content"] == ""

        resp2 = await client.get("/api/clipboard/")
        assert len(resp2.json()) == 1

    @pytest.mark.asyncio()
    async def test_delete(self, client: AsyncClient) -> None:
        resp = await client.post("/api/clipboard/", json={"title": "To Delete"})
        snippet_id = resp.json()["id"]

        resp2 = await client.delete(f"/api/clipboard/{snippet_id}")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "deleted"

        resp3 = await client.get("/api/clipboard/")
        assert resp3.json() == []

    @pytest.mark.asyncio()
    async def test_delete_nonexistent(self, client: AsyncClient) -> None:
        resp = await client.delete("/api/clipboard/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio()
    async def test_patch_title(self, client: AsyncClient) -> None:
        resp = await client.post("/api/clipboard/", json={"title": "Old"})
        snippet_id = resp.json()["id"]

        resp2 = await client.patch(
            f"/api/clipboard/{snippet_id}", json={"title": "New"}
        )
        assert resp2.status_code == 200
        assert resp2.json()["title"] == "New"
