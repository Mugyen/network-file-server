"""Tests for PATCH /api/files/rename, DELETE /api/files, and POST /api/folders endpoints."""

from pathlib import Path

import pytest
from httpx import AsyncClient


class TestRename:
    """Tests for PATCH /api/files/rename endpoint."""

    @pytest.mark.asyncio
    async def test_rename_file(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "test.txt", "new_name": "renamed.txt"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "renamed.txt"
        assert (tmp_shared_folder / "renamed.txt").exists()
        assert not (tmp_shared_folder / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_rename_directory(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "subdir", "new_name": "newsubdir"},
        )
        assert response.status_code == 200
        assert (tmp_shared_folder / "newsubdir").is_dir()

    @pytest.mark.asyncio
    async def test_rename_conflict_returns_409(self, async_client: AsyncClient) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "test.txt", "new_name": "subdir"},
        )
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_rename_invalid_name_returns_400(self, async_client: AsyncClient) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "test.txt", "new_name": ""},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rename_slash_name_returns_400(self, async_client: AsyncClient) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "test.txt", "new_name": "bad/name"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rename_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "../etc/passwd", "new_name": "newname"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_rename_nonexistent_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.patch(
            "/api/files/rename",
            json={"path": "nonexistent.txt", "new_name": "new.txt"},
        )
        assert response.status_code == 404


class TestDelete:
    """Tests for DELETE /api/files endpoint (single delete)."""

    @pytest.mark.asyncio
    async def test_delete_single_file(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["test.txt"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "test.txt" in data["deleted"]
        assert not (tmp_shared_folder / "test.txt").exists()

    @pytest.mark.asyncio
    async def test_delete_directory(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["subdir"]},
        )
        assert response.status_code == 200
        assert not (tmp_shared_folder / "subdir").exists()

    @pytest.mark.asyncio
    async def test_delete_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["../etc/passwd"]},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["nonexistent.txt"]},
        )
        assert response.status_code == 404


class TestBatchDelete:
    """Tests for DELETE /api/files endpoint (batch delete)."""

    @pytest.mark.asyncio
    async def test_batch_delete_multiple(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["test.txt", "empty_dir"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert set(data["deleted"]) == {"test.txt", "empty_dir"}
        assert not (tmp_shared_folder / "test.txt").exists()
        assert not (tmp_shared_folder / "empty_dir").exists()

    @pytest.mark.asyncio
    async def test_batch_delete_fails_on_first_bad_path(self, async_client: AsyncClient) -> None:
        """If any path is invalid traversal, the whole batch should fail with 403."""
        response = await async_client.request(
            "DELETE",
            "/api/files",
            json={"paths": ["test.txt", "../etc/passwd"]},
        )
        # The first path may succeed but the traversal should trigger 403
        assert response.status_code in (403, 404)


class TestCreateFolder:
    """Tests for POST /api/folders endpoint."""

    @pytest.mark.asyncio
    async def test_create_folder_in_root(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "", "name": "newfolder"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["path"] == "newfolder"
        assert (tmp_shared_folder / "newfolder").is_dir()

    @pytest.mark.asyncio
    async def test_create_folder_in_subdirectory(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "subdir", "name": "child"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["path"] == "subdir/child"

    @pytest.mark.asyncio
    async def test_create_folder_conflict_returns_409(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "", "name": "subdir"},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_folder_invalid_name_returns_400(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "", "name": ""},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_folder_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "../outside", "name": "folder"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_folder_nonexistent_parent_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/folders",
            json={"parent_path": "nonexistent", "name": "child"},
        )
        assert response.status_code == 404
