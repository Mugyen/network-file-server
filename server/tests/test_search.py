"""Tests for GET /api/files/search endpoint."""

import pytest
from httpx import AsyncClient


class TestSearchEndpoint:
    """Integration tests for the search endpoint."""

    @pytest.mark.asyncio
    async def test_search_returns_matching_files(
        self, async_client: AsyncClient
    ) -> None:
        """Search for 'test' finds test.txt and nested.txt."""
        response = await async_client.get(
            "/api/files/search", params={"q": "test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test"
        assert "entries" in data
        names = [e["name"] for e in data["entries"]]
        assert "test.txt" in names

    @pytest.mark.asyncio
    async def test_search_recursive(self, async_client: AsyncClient) -> None:
        """Search from root finds files in subdirectories with relative paths."""
        response = await async_client.get(
            "/api/files/search", params={"q": "nested"}
        )
        assert response.status_code == 200
        data = response.json()
        names = [e["name"] for e in data["entries"]]
        # Nested file should include path separator showing it's in a subdir
        matching = [n for n in names if "nested" in n.lower()]
        assert len(matching) > 0
        # At least one result should contain a path separator
        has_path_sep = any("/" in n or "\\" in n for n in matching)
        assert has_path_sep, f"Expected path separator in results: {matching}"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self, async_client: AsyncClient
    ) -> None:
        """Search for 'TEST' (uppercase) matches 'test.txt'."""
        response = await async_client.get(
            "/api/files/search", params={"q": "TEST"}
        )
        assert response.status_code == 200
        data = response.json()
        names = [e["name"] for e in data["entries"]]
        assert "test.txt" in names

    @pytest.mark.asyncio
    async def test_search_no_results(self, async_client: AsyncClient) -> None:
        """Search for 'nonexistent' returns empty entries list."""
        response = await async_client.get(
            "/api/files/search", params={"q": "nonexistent"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entries"] == []

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Empty search query returns 400."""
        response = await async_client.get(
            "/api/files/search", params={"q": ""}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_search_path_traversal_returns_403(
        self, async_client: AsyncClient
    ) -> None:
        """Path traversal attempt in search path returns 403."""
        response = await async_client.get(
            "/api/files/search", params={"q": "test", "path": "../etc"}
        )
        assert response.status_code == 403
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_search_returns_valid_entry_fields(
        self, async_client: AsyncClient
    ) -> None:
        """Search results contain all required FileEntry fields."""
        response = await async_client.get(
            "/api/files/search", params={"q": "test"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["entries"]) > 0
        for entry in data["entries"]:
            assert "name" in entry
            assert "size" in entry
            assert "size_display" in entry
            assert "type" in entry
            assert "modified" in entry

    @pytest.mark.asyncio
    async def test_search_with_path_param(
        self, async_client: AsyncClient
    ) -> None:
        """Search within a subdirectory returns correct path context."""
        response = await async_client.get(
            "/api/files/search", params={"q": "nested", "path": "subdir"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "subdir"
        names = [e["name"] for e in data["entries"]]
        assert "nested.txt" in names
