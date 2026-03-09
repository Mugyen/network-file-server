"""Tests for GET /api/files/download and POST /api/files/download-zip endpoints."""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from httpx import AsyncClient


class TestDownloadEndpoint:
    """Tests for single file download via GET /api/files/download."""

    @pytest.mark.asyncio
    async def test_download_file_returns_200(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "test.txt"}
        )
        assert response.status_code == 200
        assert response.content == b"hello world"

    @pytest.mark.asyncio
    async def test_download_file_content_disposition(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "test.txt"}
        )
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "test.txt" in cd

    @pytest.mark.asyncio
    async def test_download_file_content_type(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "test.txt"}
        )
        assert response.headers["content-type"] == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_download_nested_file(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "subdir/nested.txt"}
        )
        assert response.status_code == 200
        assert response.content == b"nested content"

    @pytest.mark.asyncio
    async def test_download_directory_returns_400(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "subdir"}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_download_nonexistent_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "nonexistent.txt"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.get(
            "/api/files/download", params={"path": "../etc/passwd"}
        )
        assert response.status_code == 403


class TestZipDownload:
    """Tests for batch download as ZIP via POST /api/files/download-zip."""

    @pytest.mark.asyncio
    async def test_zip_single_file(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["test.txt"]},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(BytesIO(response.content))
        assert "test.txt" in zf.namelist()
        assert zf.read("test.txt") == b"hello world"

    @pytest.mark.asyncio
    async def test_zip_multiple_files(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["test.txt", "subdir/nested.txt"]},
        )
        assert response.status_code == 200
        zf = zipfile.ZipFile(BytesIO(response.content))
        names = zf.namelist()
        assert "test.txt" in names
        assert "subdir/nested.txt" in names

    @pytest.mark.asyncio
    async def test_zip_content_disposition(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["test.txt"]},
        )
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert "download.zip" in cd

    @pytest.mark.asyncio
    async def test_zip_traversal_returns_403(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["../etc/passwd"]},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_zip_nonexistent_returns_404(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["nonexistent.txt"]},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_zip_directory(self, async_client: AsyncClient) -> None:
        response = await async_client.post(
            "/api/files/download-zip",
            json={"paths": ["subdir"]},
        )
        assert response.status_code == 200
        zf = zipfile.ZipFile(BytesIO(response.content))
        names = zf.namelist()
        matching = [n for n in names if "nested.txt" in n]
        assert len(matching) > 0
