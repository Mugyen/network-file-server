"""Tests for the server-info API endpoint.

Tests GET /api/server-info response structure and content.
"""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config


@pytest.fixture
def info_app(tmp_path: "Path") -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app configured for server-info testing."""
    from pathlib import Path

    config = ServerConfig(
        shared_folder=tmp_path,
        port=9999,
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code=None,
            relay_url=None,
    )
    set_server_config(config)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def info_client(info_app: "FastAPI") -> AsyncClient:  # type: ignore[name-defined]  # noqa: F821
    """Create an async HTTP client for server-info tests."""
    transport = ASGITransport(app=info_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


class TestServerInfoEndpoint:
    """Tests for GET /api/server-info."""

    async def test_returns_200(self, info_client: AsyncClient) -> None:
        """Endpoint must return 200 OK."""
        response = await info_client.get("/api/server-info")
        assert response.status_code == 200

    async def test_has_required_fields(self, info_client: AsyncClient) -> None:
        """Response must contain ip, port, url, qr_svg, all_ips fields."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        assert "ip" in data
        assert "port" in data
        assert "url" in data
        assert "qr_svg" in data
        assert "all_ips" in data

    async def test_ip_is_valid_ipv4(self, info_client: AsyncClient) -> None:
        """ip field must be a valid IPv4 address."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        ipv4_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
        assert ipv4_pattern.match(data["ip"]), f"'{data['ip']}' is not valid IPv4"

    async def test_port_matches_config(self, info_client: AsyncClient) -> None:
        """port field must match the configured port."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        assert data["port"] == 9999

    async def test_url_format(self, info_client: AsyncClient) -> None:
        """url must match http://{ip}:{port} format."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        expected_url = f"http://{data['ip']}:{data['port']}"
        assert data["url"] == expected_url

    async def test_qr_svg_contains_svg(self, info_client: AsyncClient) -> None:
        """qr_svg field must contain valid SVG markup."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        svg = data["qr_svg"]
        assert isinstance(svg, str)
        assert len(svg) > 0
        assert "<?xml" in svg or "<svg" in svg

    async def test_all_ips_is_list(self, info_client: AsyncClient) -> None:
        """all_ips must be a non-empty list of strings."""
        response = await info_client.get("/api/server-info")
        data = response.json()
        assert isinstance(data["all_ips"], list)
        assert len(data["all_ips"]) > 0
        for ip in data["all_ips"]:
            assert isinstance(ip, str)
