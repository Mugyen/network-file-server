from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config


@pytest.fixture
def tmp_shared_folder(tmp_path: Path) -> Path:
    """Create a temporary shared folder with sample files for testing.

    Structure:
        tmp_path/
            test.txt          (contains "hello world")
            subdir/
                nested.txt    (contains "nested content")
            empty_dir/
    """
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    subdir = tmp_path / "subdir"
    subdir.mkdir()
    nested_file = subdir / "nested.txt"
    nested_file.write_text("nested content")

    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()

    return tmp_path


@pytest.fixture
def configured_app(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with a temp shared folder configured."""
    config = ServerConfig(shared_folder=tmp_shared_folder, port=8000)
    set_server_config(config)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def async_client(configured_app: "FastAPI") -> AsyncClient:  # type: ignore[name-defined]  # noqa: F821
    """Create an async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]
