"""Integration tests for share router endpoints."""

import secrets
import time
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config
from server.app.models.enums import ShareTTL
from server.app.services.auth_service import (
    AuthTokenService,
    hash_password,
    set_token_service,
)
from server.app.services.share_service import (
    ShareLinkRecord,
    ShareLinkService,
    set_share_service,
)


# --- Fixtures ---


@pytest.fixture
def configured_app_with_shares(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with ShareLinkService initialized (no password)."""
    config = ServerConfig(
        shared_folder=tmp_shared_folder,
        port=8000,
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code=None,
            relay_url=None,
    )
    set_server_config(config)

    secret_key = secrets.token_hex(32)
    service = ShareLinkService(secret_key)
    set_share_service(service)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def share_client(
    configured_app_with_shares: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> AsyncClient:
    """Async HTTP client for the share-enabled app."""
    transport = ASGITransport(app=configured_app_with_shares)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


@pytest.fixture
def configured_app_shares_with_password(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with password + ShareLinkService."""
    password_hash = hash_password("test-password-123")
    config = ServerConfig(
        shared_folder=tmp_shared_folder,
        port=8000,
        password_hash=password_hash,
        read_only=False,
        receive=False,
        mount_code=None,
            relay_url=None,
    )
    set_server_config(config)

    secret_key = secrets.token_hex(32)
    auth_service = AuthTokenService(secret_key)
    set_token_service(auth_service)

    share_service = ShareLinkService(secret_key)
    set_share_service(share_service)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def share_client_with_password(
    configured_app_shares_with_password: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> AsyncClient:
    """Async HTTP client for password-protected share-enabled app."""
    transport = ASGITransport(app=configured_app_shares_with_password)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


# --- POST /api/shares ---


class TestCreateShareLink:
    async def test_create_share_returns_201_with_token(self, share_client: AsyncClient) -> None:
        resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert "share_url" in data
        assert data["file_name"] == "test.txt"
        assert data["ttl_seconds"] == 3600

    async def test_create_share_nonexistent_file_returns_404(self, share_client: AsyncClient) -> None:
        resp = await share_client.post(
            "/api/shares",
            json={"file_path": "nonexistent.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        assert resp.status_code == 404


# --- GET /api/shares ---


class TestListShareLinks:
    async def test_list_shares_returns_empty(self, share_client: AsyncClient) -> None:
        resp = await share_client.get("/api/shares")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_shares_returns_active_links(self, share_client: AsyncClient) -> None:
        # Create a share first
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        assert create_resp.status_code == 201

        resp = await share_client.get("/api/shares")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["file_name"] == "test.txt"


# --- DELETE /api/shares/{token} ---


class TestRevokeShareLink:
    async def test_revoke_returns_204(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        token = create_resp.json()["token"]

        resp = await share_client.delete(f"/api/shares/{token}")
        assert resp.status_code == 204

    async def test_revoke_unknown_token_returns_404(self, share_client: AsyncClient) -> None:
        resp = await share_client.delete("/api/shares/nonexistent-token")
        assert resp.status_code == 404


# --- GET /share/{token} (HTML page) ---


class TestShareDownloadPage:
    async def test_valid_token_returns_html_page(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        token = create_resp.json()["token"]

        resp = await share_client.get(f"/share/{token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "test.txt" in resp.text
        assert "Download" in resp.text

    async def test_expired_token_returns_expired_page(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.FIFTEEN_MINUTES},
        )
        token = create_resp.json()["token"]

        # Force expiry by manipulating the service record
        from server.app.services.share_service import get_share_service
        service = get_share_service()
        record = service._active_links[token]
        service._active_links[token] = ShareLinkRecord(
            token=record.token,
            file_path=record.file_path,
            created_at=record.created_at,
            ttl_seconds=1,
        )
        time.sleep(2)

        resp = await share_client.get(f"/share/{token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "expired" in resp.text.lower()

    async def test_revoked_token_returns_expired_page(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        token = create_resp.json()["token"]

        # Revoke
        await share_client.delete(f"/api/shares/{token}")

        resp = await share_client.get(f"/share/{token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "expired" in resp.text.lower()

    async def test_file_deleted_after_link_creation_shows_unavailable(
        self, share_client: AsyncClient, tmp_shared_folder: Path
    ) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        token = create_resp.json()["token"]

        # Delete the actual file
        (tmp_shared_folder / "test.txt").unlink()

        resp = await share_client.get(f"/share/{token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "unavailable" in resp.text.lower() or "no longer" in resp.text.lower()


# --- GET /share/{token}/download ---


class TestShareFileDownload:
    async def test_download_returns_file(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
        )
        token = create_resp.json()["token"]

        resp = await share_client.get(f"/share/{token}/download")
        assert resp.status_code == 200
        assert resp.text == "hello world"

    async def test_download_expired_returns_expired_page(self, share_client: AsyncClient) -> None:
        create_resp = await share_client.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.FIFTEEN_MINUTES},
        )
        token = create_resp.json()["token"]

        # Force expiry
        from server.app.services.share_service import get_share_service
        service = get_share_service()
        record = service._active_links[token]
        service._active_links[token] = ShareLinkRecord(
            token=record.token,
            file_path=record.file_path,
            created_at=record.created_at,
            ttl_seconds=1,
        )
        time.sleep(2)

        resp = await share_client.get(f"/share/{token}/download")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "expired" in resp.text.lower()


# --- Auth bypass (SHARE-05) ---


class TestShareAuthBypass:
    async def test_share_page_accessible_without_session_cookie(
        self, share_client_with_password: AsyncClient
    ) -> None:
        """Share link pages should be accessible without a session cookie on password-protected server."""
        # First create a share (need auth for API)
        from server.app.services.auth_service import get_token_service
        token_service = get_token_service()
        session_token = token_service.create_token()

        create_resp = await share_client_with_password.post(
            "/api/shares",
            json={"file_path": "test.txt", "ttl": ShareTTL.ONE_HOUR},
            cookies={"session": session_token},
        )
        assert create_resp.status_code == 201
        share_token = create_resp.json()["token"]

        # Now access the share page WITHOUT a session cookie
        resp = await share_client_with_password.get(f"/share/{share_token}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "test.txt" in resp.text

    async def test_api_shares_requires_auth(
        self, share_client_with_password: AsyncClient
    ) -> None:
        """API endpoints should still require auth on password-protected server."""
        resp = await share_client_with_password.get("/api/shares")
        assert resp.status_code == 401
