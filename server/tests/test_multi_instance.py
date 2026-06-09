"""Phase-6 DI guarantees: multiple app instances coexist in one process.

Before the singleton retirement, the second create_app() overwrote the
first app's config/services (the agent literally mutated server globals on
every reconnect). These tests pin the new behavior.
"""

from pathlib import Path

from starlette.testclient import TestClient

from server.app.config import ServerConfig, create_default_config
from server.app.main import create_app


def _make_app(folder: Path, port: int):
    folder.mkdir(parents=True, exist_ok=True)
    return create_app(create_default_config(shared_folder=folder, port=port))


class TestMultiInstance:
    def test_two_apps_have_independent_state(self, tmp_path: Path) -> None:
        app_a = _make_app(tmp_path / "a" / "shared", 8001)
        app_b = _make_app(tmp_path / "b" / "shared", 8002)

        assert app_a.state.config is not app_b.state.config
        assert app_a.state.config.port == 8001
        assert app_b.state.config.port == 8002
        assert app_a.state.manager is not app_b.state.manager
        assert app_a.state.share_service is not app_b.state.share_service
        assert app_a.state.clipboard_service is not app_b.state.clipboard_service

    def test_two_apps_serve_their_own_folders(self, tmp_path: Path) -> None:
        folder_a = tmp_path / "a" / "shared"
        folder_b = tmp_path / "b" / "shared"
        app_a = _make_app(folder_a, 8001)
        app_b = _make_app(folder_b, 8002)
        (folder_a / "only-in-a.txt").write_text("a")
        (folder_b / "only-in-b.txt").write_text("b")

        names_a = [
            e["name"]
            for e in TestClient(app_a).get("/api/files?path=").json()["entries"]
        ]
        names_b = [
            e["name"]
            for e in TestClient(app_b).get("/api/files?path=").json()["entries"]
        ]
        assert names_a == ["only-in-a.txt"]
        assert names_b == ["only-in-b.txt"]

    def test_password_app_does_not_leak_auth_into_open_app(self, tmp_path: Path) -> None:
        """An open app stays open even when a password-protected app exists —
        the old global token service made this ordering-dependent."""
        from server.app.services.auth_service import hash_password

        open_folder = tmp_path / "open" / "shared"
        open_folder.mkdir(parents=True)
        locked_folder = tmp_path / "locked" / "shared"
        locked_folder.mkdir(parents=True)

        locked_app = create_app(
            ServerConfig(
                shared_folder=locked_folder,
                port=8003,
                password_hash=hash_password("secret-pw"),
                read_only=False,
                receive=False,
                mount_code=None,
                relay_url=None,
            )
        )
        open_app = _make_app(open_folder, 8004)

        assert locked_app.state.token_service is not None
        assert open_app.state.token_service is None

        # Open app serves without auth; locked app rejects unauthenticated API
        assert TestClient(open_app).get("/api/files?path=").status_code == 200
        assert TestClient(locked_app).get("/api/files?path=").status_code == 401

    def test_dependency_override_seam(self, tmp_path: Path) -> None:
        """FastAPI dependency_overrides can replace a service per-app (the
        DI seam tests use instead of resetting global state)."""
        from server.app.dependencies import get_share_service
        from server.app.services.share_service import ShareLinkService

        app = _make_app(tmp_path / "shared", 8005)
        replacement = ShareLinkService("override-secret")
        app.dependency_overrides[get_share_service] = lambda: replacement

        client = TestClient(app)
        response = client.get("/api/shares")
        assert response.status_code == 200
        assert response.json() == []
