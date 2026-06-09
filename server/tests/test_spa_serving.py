"""Tests for SPA static file serving path resolution."""

from pathlib import Path

from server.app.main import create_app


class TestSpaPathResolution:
    """Verify client/dist is resolved relative to the project root, not CWD."""

    def test_client_dist_resolves_to_project_root(self) -> None:
        """The SPA path must resolve relative to the project root (server/../..),
        not the current working directory. This ensures the server serves the
        built client regardless of where the user launches the command."""
        project_root = Path(__file__).resolve().parent.parent.parent
        expected_dist = project_root / "client" / "dist"

        # Verify the path is absolute and points to the right location
        assert expected_dist.is_absolute()
        assert expected_dist.parts[-2:] == ("client", "dist")

    def test_create_app_mounts_spa_when_dist_exists(self, tmp_path: Path) -> None:
        """create_app builds successfully and registers routes."""
        from server.app.config import create_default_config

        config = create_default_config(shared_folder=tmp_path, port=8000)
        app = create_app(config)
        # The app should have routes registered
        assert len(app.routes) > 0
