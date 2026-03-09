"""Tests for GET /api/files/preview endpoint."""

import pytest
from httpx import AsyncClient


class TestPreviewEndpoint:
    """Integration tests for the file preview endpoint."""

    @pytest.mark.asyncio
    async def test_preview_serves_text_file(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of text file returns 200 with text/plain and inline disposition."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "test.txt"}
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert content_type.startswith("text/plain"), (
            f"Expected text/plain, got {content_type}"
        )
        disposition = response.headers.get("content-disposition", "")
        assert "inline" in disposition
        assert "test.txt" in disposition

    @pytest.mark.asyncio
    async def test_preview_serves_image(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of PNG image returns 200 with image/png Content-Type."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "image.png"}
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "image/png" in content_type, (
            f"Expected image/png, got {content_type}"
        )

    @pytest.mark.asyncio
    async def test_preview_serves_code_file(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of .py file returns 200 with correct content."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "code.py"}
        )
        assert response.status_code == 200
        # Python files should get a text MIME type
        content_type = response.headers.get("content-type", "")
        assert "text" in content_type or "python" in content_type

    @pytest.mark.asyncio
    async def test_preview_serves_markdown(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of .md file returns 200."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "doc.md"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_preview_range_request(
        self, async_client: AsyncClient
    ) -> None:
        """Range request returns 206 Partial Content with Content-Range header."""
        response = await async_client.get(
            "/api/files/preview",
            params={"path": "video.mp4"},
            headers={"Range": "bytes=0-4"},
        )
        assert response.status_code == 206
        content_range = response.headers.get("content-range", "")
        assert content_range.startswith("bytes"), (
            f"Expected Content-Range header, got: {content_range}"
        )

    @pytest.mark.asyncio
    async def test_preview_nonexistent_returns_404(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of non-existent file returns 404."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "missing.txt"}
        )
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_preview_directory_returns_400(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of a directory returns 400."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "subdir"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_preview_path_traversal_returns_403(
        self, async_client: AsyncClient
    ) -> None:
        """Path traversal attempt in preview returns 403."""
        response = await async_client.get(
            "/api/files/preview",
            params={"path": "../../etc/passwd"},
        )
        assert response.status_code == 403
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_preview_video_mime_type(
        self, async_client: AsyncClient
    ) -> None:
        """Preview of .mp4 returns video/mp4 Content-Type."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "video.mp4"}
        )
        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "video/mp4" in content_type, (
            f"Expected video/mp4, got {content_type}"
        )

    @pytest.mark.asyncio
    async def test_preview_inline_disposition(
        self, async_client: AsyncClient
    ) -> None:
        """Preview Content-Disposition is inline (not attachment)."""
        response = await async_client.get(
            "/api/files/preview", params={"path": "test.txt"}
        )
        assert response.status_code == 200
        disposition = response.headers.get("content-disposition", "")
        assert "inline" in disposition
        assert "attachment" not in disposition
