import pytest
from httpx import AsyncClient


class TestFilesRoute:
    """Tests for GET /api/files endpoint."""

    @pytest.mark.asyncio
    async def test_list_root_returns_200(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/files")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_root_returns_directory_listing(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get("/api/files")
        data = response.json()
        assert "path" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)

    @pytest.mark.asyncio
    async def test_list_root_contains_test_files(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get("/api/files")
        data = response.json()
        names = [e["name"] for e in data["entries"]]
        assert "test.txt" in names
        assert "subdir" in names
        assert "empty_dir" in names

    @pytest.mark.asyncio
    async def test_list_subdirectory(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/files", params={"path": "subdir"})
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "subdir"
        names = [e["name"] for e in data["entries"]]
        assert "nested.txt" in names

    @pytest.mark.asyncio
    async def test_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.get("/api/files", params={"path": "../etc"})
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_nonexistent_returns_404(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get(
            "/api/files", params={"path": "nonexistent"}
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_entry_has_required_fields(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get("/api/files")
        data = response.json()
        for entry in data["entries"]:
            assert "name" in entry
            assert "size" in entry
            assert "size_display" in entry
            assert "type" in entry
            assert "modified" in entry
