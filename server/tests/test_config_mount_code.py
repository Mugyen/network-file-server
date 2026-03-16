"""Tests for ServerConfig.mount_code field — backward compat and remote mount mode."""

import argparse
from pathlib import Path

import pytest

from server.app.config import (
    ServerConfig,
    create_config_from_args,
    create_default_config,
)


class TestServerConfigMountCode:
    """ServerConfig stores mount_code for remote mounts."""

    def test_mount_code_none_works(self, tmp_path: Path) -> None:
        """ServerConfig with mount_code=None works (LAN mode backward compat)."""
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=None,
            read_only=False,
            receive=False,
            mount_code=None,
            relay_url=None,
        )
        assert config.mount_code is None

    def test_mount_code_string_stored(self, tmp_path: Path) -> None:
        """ServerConfig with mount_code='ABC12345' stores it correctly."""
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=None,
            read_only=False,
            receive=False,
            mount_code="ABC12345",
            relay_url=None,
        )
        assert config.mount_code == "ABC12345"

    def test_create_default_config_has_none_mount_code(self, tmp_path: Path) -> None:
        """create_default_config produces config with mount_code=None."""
        config = create_default_config(shared_folder=tmp_path, port=8000)
        assert config.mount_code is None

    def test_create_config_from_args_has_none_mount_code(self, tmp_path: Path) -> None:
        """create_config_from_args produces config with mount_code=None."""
        args = argparse.Namespace(
            folder=str(tmp_path),
            port=9000,
            password_hash=None,
            read_only=False,
            receive=False,
        )
        config = create_config_from_args(args)
        assert config.mount_code is None
