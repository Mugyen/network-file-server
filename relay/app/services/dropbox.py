"""Drop box service -- creates the in-process file server for the always-on drop box mount.

The drop box is a local server app backed by a directory on the relay's
persistent disk. It is served to browsers as a LocalAsgiMount (in-process
ASGI forwarding), not through a tunnel connection. The mount lives on
``RelayState.local_mounts`` — the proxy has no drop-box-specific code.
"""

from pathlib import Path

from relay.app.services.local_mount import LocalAsgiMount
from server import ServerConfig, create_app


async def init_dropbox(data_dir: Path, dropbox_code: str) -> LocalAsgiMount:
    """Create the drop box server app wrapped as a LocalAsgiMount.

    Creates the drop box directory if it doesn't exist, configures a
    ServerConfig pointing at it, and wraps the resulting FastAPI app as a
    LocalAsgiMount ready for registration on RelayState.local_mounts.

    Args:
        data_dir: Root data directory (e.g. /data/). Drop box files go in data_dir/dropbox/.
        dropbox_code: The reserved mount code for the drop box.

    Returns:
        The LocalAsgiMount; the caller owns its lifecycle (``aclose()``).
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
        # Local mount: never trusts X-WFS-* identity (no allowlist, anonymous).
        identity_secret=None,
    )
    return LocalAsgiMount(code=dropbox_code, app=create_app(config))
