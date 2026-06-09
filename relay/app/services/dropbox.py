"""Drop box service -- creates and manages the in-process file server for the always-on drop box mount.

The drop box is a local server app backed by a directory on the relay's
persistent disk. It's served to browsers via httpx.ASGITransport forwarding
from mount_proxy, not through a tunnel connection.
"""

from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from server import ServerConfig, create_app

_dropbox_client: AsyncClient | None = None
_dropbox_app: Any = None


async def init_dropbox(data_dir: Path, dropbox_code: str) -> AsyncClient:
    """Create the drop box server app and return an httpx client for in-process forwarding.

    Creates the drop box directory if it doesn't exist, configures a ServerConfig
    pointing at it, and wraps the server's FastAPI app in an httpx.ASGITransport
    client for request forwarding.

    Args:
        data_dir: Root data directory (e.g. /data/). Drop box files go in data_dir/dropbox/.
        dropbox_code: The reserved mount code for the drop box.

    Returns:
        An httpx.AsyncClient backed by the server app's ASGI transport.
    """
    dropbox_dir = data_dir / "dropbox"
    dropbox_dir.mkdir(parents=True, exist_ok=True)

    config = ServerConfig(
        shared_folder=dropbox_dir,
        port=0,
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code=dropbox_code,
        relay_url=None,
    )
    server_app = create_app(config)
    set_dropbox_app(server_app)
    transport = ASGITransport(app=server_app)
    client = AsyncClient(transport=transport, base_url="http://dropbox")
    return client


def get_dropbox_client() -> AsyncClient | None:
    """Return the drop box httpx client, or None if drop box is not initialized."""
    return _dropbox_client


def set_dropbox_client(client: AsyncClient | None) -> None:
    """Install the drop box httpx client singleton."""
    global _dropbox_client
    _dropbox_client = client


def get_dropbox_app() -> Any:
    """Return the raw ASGI app for the drop box server.

    Required by the WebSocket bridge in mount_proxy to create
    ASGIWebSocketTransport connections.

    Raises:
        RuntimeError: If init_dropbox() has not been called.
    """
    if _dropbox_app is None:
        raise RuntimeError("Drop box app not initialized. Call init_dropbox() first.")
    return _dropbox_app


def set_dropbox_app(app: Any) -> None:
    """Install the drop box ASGI app singleton."""
    global _dropbox_app
    _dropbox_app = app
