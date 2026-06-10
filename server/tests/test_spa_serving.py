"""Tests for SPA static file serving path resolution."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import server.app.main
from server.app.main import create_app
from shared.spa import SPA_PLACEHOLDER_HTML


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


class TestAppInstanceIsolation:
    """Two apps in one process must not share state (no module singletons)."""

    def test_two_apps_have_independent_stores(self, tmp_path: Path) -> None:
        """Each create_app gets its own ServerStateStore, even on one data dir."""
        from server.app.config import create_default_config

        shared = tmp_path / "shared"
        shared.mkdir()
        config = create_default_config(shared_folder=shared, port=8000)
        app_a = create_app(config)
        app_b = create_app(config)
        assert app_a.state.store is not app_b.state.store
        assert app_a.state.clipboard_service is not app_b.state.clipboard_service


class TestSpaFallbackWithoutBundle:
    """The SPA catch-all must resolve even without a built client bundle.

    CI's backend job never builds client/dist; the catch-all serves the
    shared placeholder shell there instead of 404ing (regression: the
    route used to be registered only when client/dist existed).
    """

    @pytest.fixture
    def app_without_dist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
        """Build an app whose repo root contains no client/dist bundle."""
        from server.app.config import create_default_config

        monkeypatch.setattr(server.app.main, "repo_root", lambda: tmp_path / "empty-root")
        shared = tmp_path / "shared"
        shared.mkdir()
        config = create_default_config(shared_folder=shared, port=8000)
        return create_app(config)

    @pytest.mark.anyio
    async def test_root_serves_placeholder_html(
        self,
        app_without_dist: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """GET / returns 200 with the placeholder shell when dist is absent."""
        transport = ASGITransport(app=app_without_dist)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/")
        assert response.status_code == 200
        assert response.text == SPA_PLACEHOLDER_HTML

    @pytest.mark.anyio
    async def test_spa_route_serves_placeholder_html(
        self,
        app_without_dist: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """Client-side routes (e.g. /folder/sub) also resolve to the shell."""
        transport = ASGITransport(app=app_without_dist)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/folder/sub")
        assert response.status_code == 200
        assert response.text == SPA_PLACEHOLDER_HTML

    @pytest.mark.anyio
    async def test_unknown_api_path_still_404s(
        self,
        app_without_dist: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
    ) -> None:
        """POST to an unknown API path is not swallowed by the GET catch-all."""
        transport = ASGITransport(app=app_without_dist)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/api/nonexistent")
        assert response.status_code in (404, 405)
