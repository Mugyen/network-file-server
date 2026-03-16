import secrets
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config
from server.app.services.auth_service import (
    AuthTokenService,
    hash_password,
    set_token_service,
)


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

    # Sample files for preview testing
    # Minimal valid PNG: magic bytes + IHDR chunk (enough for MIME detection by extension)
    png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    image_file = tmp_path / "image.png"
    image_file.write_bytes(png_magic)

    code_file = tmp_path / "code.py"
    code_file.write_text('print("hello")')

    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Hello\n\nWorld")

    # Dummy video file (MIME detection uses extension, not content)
    video_file = tmp_path / "video.mp4"
    video_file.write_bytes(b"\x00" * 64)

    return tmp_path


@pytest.fixture
def configured_app(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with a temp shared folder configured.

    Uses default access control settings: no password, not read-only, not receive.
    """
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

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def async_client(configured_app: "FastAPI") -> AsyncClient:  # type: ignore[name-defined]  # noqa: F821
    """Create an async HTTP client for testing the FastAPI app."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


# --- Password-protected app fixtures ---

# Fixed test password for deterministic test behavior
TEST_PASSWORD = "test-password-123"


def get_valid_session_cookie(token_service: AuthTokenService) -> str:
    """Create a valid session cookie value for authenticated test requests."""
    return token_service.create_token()


@pytest.fixture
def configured_app_with_password(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app with password protection enabled."""
    password_hash = hash_password(TEST_PASSWORD)
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

    # 32-byte hex secret for signing session tokens in tests
    secret_key = secrets.token_hex(32)
    service = AuthTokenService(secret_key)
    set_token_service(service)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def async_client_with_password(
    configured_app_with_password: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> AsyncClient:
    """Create an async HTTP client for a password-protected app."""
    transport = ASGITransport(app=configured_app_with_password)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


# --- Read-only app fixtures ---


@pytest.fixture
def configured_app_read_only(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app in read-only mode."""
    config = ServerConfig(
        shared_folder=tmp_shared_folder,
        port=8000,
        password_hash=None,
        read_only=True,
        receive=False,
        mount_code=None,
            relay_url=None,
    )
    set_server_config(config)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def async_client_read_only(
    configured_app_read_only: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> AsyncClient:
    """Create an async HTTP client for a read-only app."""
    transport = ASGITransport(app=configured_app_read_only)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]


# --- Receive-only app fixtures ---


@pytest.fixture
def configured_app_receive(tmp_shared_folder: Path) -> "FastAPI":  # type: ignore[name-defined]  # noqa: F821
    """Create a FastAPI app in receive-only mode."""
    config = ServerConfig(
        shared_folder=tmp_shared_folder,
        port=8000,
        password_hash=None,
        read_only=False,
        receive=True,
        mount_code=None,
            relay_url=None,
    )
    set_server_config(config)

    from server.app.main import create_app

    return create_app()


@pytest.fixture
async def async_client_receive(
    configured_app_receive: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> AsyncClient:
    """Create an async HTTP client for a receive-mode app."""
    transport = ASGITransport(app=configured_app_receive)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # type: ignore[misc]
