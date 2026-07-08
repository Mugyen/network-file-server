"""Tests for POST /api/files/upload endpoint."""

from pathlib import Path

import pytest
from httpx import AsyncClient


class TestUploadEndpoint:
    """Tests for file upload via POST /api/files/upload."""

    @pytest.mark.asyncio
    async def test_upload_single_file(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "overwrite"},
            files={"files": ("upload_test.txt", b"uploaded content", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "upload_test.txt"
        assert data[0]["skipped"] is False
        assert (tmp_shared_folder / "upload_test.txt").read_bytes() == b"uploaded content"

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "overwrite"},
            files=[
                ("files", ("file_a.txt", b"content a", "text/plain")),
                ("files", ("file_b.txt", b"content b", "text/plain")),
            ],
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert names == {"file_a.txt", "file_b.txt"}

    @pytest.mark.asyncio
    async def test_upload_to_subdirectory(self, async_client: AsyncClient, tmp_shared_folder: Path) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "subdir", "conflict_resolution": "overwrite"},
            files={"files": ("sub_upload.txt", b"sub data", "text/plain")},
        )
        assert response.status_code == 200
        assert (tmp_shared_folder / "subdir" / "sub_upload.txt").exists()

    @pytest.mark.asyncio
    async def test_upload_conflict_no_resolution_returns_409(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        """Uploading an existing file without conflict_resolution returns 409."""
        response = await async_client.post(
            "/api/files/upload",
            params={"path": ""},
            files={"files": ("test.txt", b"conflict attempt", "text/plain")},
        )
        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_upload_overwrite_replaces(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "overwrite"},
            files={"files": ("test.txt", b"overwritten", "text/plain")},
        )
        assert response.status_code == 200
        assert (tmp_shared_folder / "test.txt").read_bytes() == b"overwritten"

    @pytest.mark.asyncio
    async def test_upload_rename_creates_suffixed_file(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "rename"},
            files={"files": ("test.txt", b"renamed copy", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data[0]["name"] == "test_1.txt"

    @pytest.mark.asyncio
    async def test_upload_skip_preserves_original(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "skip"},
            files={"files": ("test.txt", b"skipped data", "text/plain")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data[0]["skipped"] is True
        assert (tmp_shared_folder / "test.txt").read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_upload_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "../outside", "conflict_resolution": "overwrite"},
            files={"files": ("evil.txt", b"malicious", "text/plain")},
        )
        assert response.status_code == 403

    @pytest.mark.parametrize(
        "filename",
        [
            "../escape-upload.txt",
            "subdir/escape-upload.txt",
            "..\\escape-upload.txt",
        ],
    )
    @pytest.mark.asyncio
    async def test_upload_invalid_filename_returns_400(
        self,
        async_client: AsyncClient,
        tmp_shared_folder: Path,
        filename: str,
    ) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "", "conflict_resolution": "overwrite"},
            files={"files": (filename, b"malicious", "text/plain")},
        )
        assert response.status_code == 400
        assert not (tmp_shared_folder.parent / "escape-upload.txt").exists()
        assert not (tmp_shared_folder / "subdir" / "escape-upload.txt").exists()

    @pytest.mark.asyncio
    async def test_upload_nonexistent_dir_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/upload",
            params={"path": "nonexistent_dir", "conflict_resolution": "overwrite"},
            files={"files": ("file.txt", b"data", "text/plain")},
        )
        assert response.status_code == 404
