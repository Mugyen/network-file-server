"""Server configuration module.

Provides ServerConfig for holding validated server settings. The config is
attached to the FastAPI app (``app.state.config``) by ``create_app`` —
there is deliberately no module-level config global, so multiple app
instances can coexist in one process (LAN server + relay drop box, tests).
"""

import argparse
from pathlib import Path


class ServerConfig:
    """Holds validated server configuration.

    Validates that shared_folder exists and is a directory on construction.
    Raises ValueError if validation fails.
    """

    shared_folder: Path
    port: int
    password_hash: bytes | None
    read_only: bool
    receive: bool
    mount_code: str | None
    relay_url: str | None

    def __init__(
        self,
        shared_folder: Path,
        port: int,
        password_hash: bytes | None,
        read_only: bool,
        receive: bool,
        mount_code: str | None,
        relay_url: str | None,
    ) -> None:
        if not shared_folder.exists():
            raise ValueError(
                f"Shared folder '{shared_folder}' does not exist"
            )
        if not shared_folder.is_dir():
            raise ValueError(
                f"Shared folder '{shared_folder}' is not a directory"
            )
        self.shared_folder = shared_folder.resolve()
        self.port = port
        self.password_hash = password_hash
        self.read_only = read_only
        self.receive = receive
        self.mount_code = mount_code
        self.relay_url = relay_url


def create_default_config(shared_folder: Path, port: int) -> ServerConfig:
    """Create a ServerConfig with default access control settings.

    password_hash=None: no password protection (open access)
    read_only=False: all operations allowed
    receive=False: receive-only mode disabled
    """
    return ServerConfig(
        shared_folder=shared_folder,
        port=port,
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code=None,
        relay_url=None,
    )


def create_config_from_args(args: argparse.Namespace) -> ServerConfig:
    """Construct a ServerConfig from parsed CLI arguments.

    Expects args to have 'folder' (str), 'port' (int), 'password_hash' (bytes | None),
    'read_only' (bool), and 'receive' (bool) attributes.
    """
    folder_path = Path(args.folder).resolve()
    return ServerConfig(
        shared_folder=folder_path,
        port=args.port,
        password_hash=args.password_hash,
        read_only=args.read_only,
        receive=args.receive,
        mount_code=None,
        relay_url=None,
    )
