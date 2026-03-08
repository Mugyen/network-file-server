"""Server configuration module.

Provides ServerConfig for holding validated server settings,
and module-level get/set functions for global config access.
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

    def __init__(self, shared_folder: Path, port: int) -> None:
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


_config: ServerConfig | None = None


def get_server_config() -> ServerConfig:
    """Return the current server config. Raises RuntimeError if not set."""
    global _config
    if _config is None:
        raise RuntimeError("Server config has not been set. Call set_server_config() first.")
    return _config


def set_server_config(config: ServerConfig) -> None:
    """Set the global server config."""
    global _config
    _config = config


def create_config_from_args(args: argparse.Namespace) -> ServerConfig:
    """Construct a ServerConfig from parsed CLI arguments.

    Expects args to have 'folder' (str) and 'port' (int) attributes.
    """
    folder_path = Path(args.folder).resolve()
    return ServerConfig(shared_folder=folder_path, port=args.port)
