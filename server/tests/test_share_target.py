"""Tests for POST /api/share-upload (Web Share Target endpoint)."""

from pathlib import Path

import pytest
from httpx import AsyncClient


class TestShareTargetEndpoint:
    """Tests for files shared via the PWA share sheet."""

    @pytest.mark.asyncio
    async def test_share_single_file_writes_to_root_and_redirects(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        """A single shared file is written to the shared folder root and the
        response is a 303 redirect to ../ so the browser returns to the SPA."""
        response = await async_client.post(
            "/api/share-upload",
            files={"files": ("photo.jpg", b"jpegbytes", "image/jpeg")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "../"
        assert (tmp_shared_folder / "photo.jpg").read_bytes() == b"jpegbytes"

    @pytest.mark.asyncio
    async def test_share_multiple_files_all_saved(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        """Sharing multiple files in one POST writes every one to disk."""
        response = await async_client.post(
            "/api/share-upload",
            files=[
                ("files", ("a.txt", b"AA", "text/plain")),
                ("files", ("b.txt", b"BB", "text/plain")),
            ],
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert (tmp_shared_folder / "a.txt").read_bytes() == b"AA"
        assert (tmp_shared_folder / "b.txt").read_bytes() == b"BB"

    @pytest.mark.asyncio
    async def test_share_existing_filename_auto_renames(
        self, async_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        """When the shared file's name already exists, the new file is saved
        with a numeric suffix so the share never fails."""
        (tmp_shared_folder / "note.txt").write_bytes(b"original")

        response = await async_client.post(
            "/api/share-upload",
            files={"files": ("note.txt", b"newer", "text/plain")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert (tmp_shared_folder / "note.txt").read_bytes() == b"original"
        assert (tmp_shared_folder / "note_1.txt").read_bytes() == b"newer"

    @pytest.mark.asyncio
    async def test_share_without_files_rejected(
        self, async_client: AsyncClient
    ) -> None:
        """POST without a files field should fail rather than silently succeed."""
        response = await async_client.post(
            "/api/share-upload",
            data={"title": "some title"},
            follow_redirects=False,
        )
        # FastAPI returns 422 when the required files field is missing.
        assert response.status_code == 422
