"""Server configuration module -- stub for TDD RED phase."""

import argparse
from pathlib import Path


class ServerConfig:
    """Holds server configuration. Stub -- not yet implemented."""

    def __init__(self, shared_folder: Path, port: int) -> None:
        raise NotImplementedError("ServerConfig not yet implemented")


_config: ServerConfig | None = None


def get_server_config() -> ServerConfig:
    raise NotImplementedError("get_server_config not yet implemented")


def set_server_config(config: ServerConfig) -> None:
    raise NotImplementedError("set_server_config not yet implemented")


def create_config_from_args(args: argparse.Namespace) -> ServerConfig:
    raise NotImplementedError("create_config_from_args not yet implemented")
