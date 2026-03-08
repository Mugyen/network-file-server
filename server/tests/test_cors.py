import pytest
from httpx import AsyncClient


class TestCORS:
    """Tests for CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_get_includes_cors_header(
        self, async_client: AsyncClient
    ) -> None:
        response = await async_client.get(
            "/api/files",
            headers={"origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_options_preflight(self, async_client: AsyncClient) -> None:
        response = await async_client.options(
            "/api/files",
            headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
