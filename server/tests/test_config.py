import argparse
from pathlib import Path

import bcrypt
import pytest

from server.app.config import (
    ServerConfig,
    create_config_from_args,
    create_default_config,
)


class TestServerConfig:
    """Tests for ServerConfig validation."""

    def test_valid_folder(self, tmp_path: Path) -> None:
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=None,
            read_only=False,
            receive=False,
        )
        assert config.shared_folder == tmp_path
        assert config.port == 8000

    def test_nonexistent_folder_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            ServerConfig(
                shared_folder=nonexistent,
                port=8000,
                password_hash=None,
                read_only=False,
                receive=False,
            )

    def test_file_instead_of_directory_raises(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a_file.txt"
        file_path.write_text("content")
        with pytest.raises(ValueError, match="not a directory"):
            ServerConfig(
                shared_folder=file_path,
                port=8000,
                password_hash=None,
                read_only=False,
                receive=False,
            )

    def test_stores_password_hash(self, tmp_path: Path) -> None:
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt())
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=hashed,
            read_only=False,
            receive=False,
        )
        assert config.password_hash == hashed

    def test_stores_read_only(self, tmp_path: Path) -> None:
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=None,
            read_only=True,
            receive=False,
        )
        assert config.read_only is True

    def test_stores_receive(self, tmp_path: Path) -> None:
        config = ServerConfig(
            shared_folder=tmp_path,
            port=8000,
            password_hash=None,
            read_only=False,
            receive=True,
        )
        assert config.receive is True


class TestCreateDefaultConfig:
    """Tests for create_default_config factory function."""

    def test_defaults(self, tmp_path: Path) -> None:
        config = create_default_config(shared_folder=tmp_path, port=8000)
        assert config.password_hash is None
        assert config.read_only is False
        assert config.receive is False
        assert config.shared_folder == tmp_path
        assert config.port == 8000


class TestCreateConfigFromArgs:
    """Tests for create_config_from_args."""

    def test_maps_new_fields(self, tmp_path: Path) -> None:
        hashed = bcrypt.hashpw(b"test", bcrypt.gensalt())
        args = argparse.Namespace(
            folder=str(tmp_path),
            port=9000,
            password_hash=hashed,
            read_only=True,
            receive=False,
        )
        config = create_config_from_args(args)
        assert config.password_hash == hashed
        assert config.read_only is True
        assert config.receive is False


class TestExceptions:
    """Tests for access control exception types."""

    def test_access_denied_error_message(self) -> None:
        from server.app.exceptions import AccessDeniedError

        err = AccessDeniedError("Invalid credentials")
        assert str(err) == "Invalid credentials"

    def test_read_only_error_stores_operation(self) -> None:
        from server.app.exceptions import ReadOnlyError

        err = ReadOnlyError("upload")
        assert err.operation == "upload"
        assert "upload" in str(err)

    def test_exceptions_are_distinct_types(self) -> None:
        from server.app.exceptions import AccessDeniedError, ReadOnlyError

        assert not issubclass(AccessDeniedError, ReadOnlyError)
        assert not issubclass(ReadOnlyError, AccessDeniedError)
