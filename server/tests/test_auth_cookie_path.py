"""Tests for cookie path scoping in auth router based on mount_code."""

from pathlib import Path

from starlette.testclient import TestClient

from server.app.config import ServerConfig
from server.app.main import create_app
from server.app.services.auth_service import hash_password

TEST_PASSWORD = "test-auth-cookie-password"


def _make_app(tmp_path: Path, mount_code: str | None) -> "object":
    """Create a FastAPI app with password + optional mount_code."""
    password_hash = hash_password(TEST_PASSWORD)
    config = ServerConfig(
        shared_folder=tmp_path,
        port=8000,
        password_hash=password_hash,
        read_only=False,
        receive=False,
        mount_code=mount_code,
        relay_url=None,
    )
    return create_app(config)


class TestLoginCookiePath:
    """Cookie path is scoped by mount_code on login and logout."""

    def test_login_no_mount_code_sets_root_path(self, tmp_path: Path) -> None:
        """auth login with mount_code=None sets cookie path='/'."""
        app = _make_app(tmp_path, mount_code=None)
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
        assert response.status_code == 200
        # Check the Set-Cookie header for path
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "Path=/" in set_cookie_header

    def test_login_with_mount_code_sets_scoped_path(self, tmp_path: Path) -> None:
        """auth login with mount_code='ABC12345' sets cookie path='/m/ABC12345/'."""
        app = _make_app(tmp_path, mount_code="ABC12345")
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"password": TEST_PASSWORD})
        assert response.status_code == 200
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "Path=/m/ABC12345/" in set_cookie_header

    def test_logout_no_mount_code_clears_root_path(self, tmp_path: Path) -> None:
        """auth logout with mount_code=None clears cookie at path='/'."""
        app = _make_app(tmp_path, mount_code=None)
        client = TestClient(app)
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "Path=/" in set_cookie_header

    def test_logout_with_mount_code_clears_scoped_path(self, tmp_path: Path) -> None:
        """auth logout with mount_code='ABC12345' clears cookie at path='/m/ABC12345/'."""
        app = _make_app(tmp_path, mount_code="ABC12345")
        client = TestClient(app)
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        set_cookie_header = response.headers.get("set-cookie", "")
        assert "Path=/m/ABC12345/" in set_cookie_header
