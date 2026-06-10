"""Drop box service -- creates the in-process file server for the always-on drop box mount.

The drop box is a local server app backed by a directory on the relay's
persistent disk. It's served to browsers via httpx.ASGITransport forwarding
from mount_proxy, not through a tunnel connection. Both the app and the
client live on RelayState (app.state.relay) — no module-level singletons.
"""

from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

from server import ServerConfig, create_app


async def init_dropbox(data_dir: Path, dropbox_code: str) -> tuple[Any, AsyncClient]:
    """Create the drop box server app and an httpx client for in-process forwarding.

    Creates the drop box directory if it doesn't exist, configures a ServerConfig
    pointing at it, and wraps the server's FastAPI app in an httpx.ASGITransport
    client for request forwarding.

    Args:
        data_dir: Root data directory (e.g. /data/). Drop box files go in data_dir/dropbox/.
        dropbox_code: The reserved mount code for the drop box.

    Returns:
        ``(server_app, client)`` — the drop box ASGI app (needed by the
        WebSocket bridge in mount_proxy) and an httpx.AsyncClient backed by
        its ASGI transport. The caller owns both lifecycles.
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
    transport = ASGITransport(app=server_app)
    client = AsyncClient(transport=transport, base_url="http://dropbox")
    return server_app, client
