from pathlib import Path

import pytest

from server.app.config import ServerConfig


class TestServerConfig:
    """Tests for ServerConfig validation."""

    def test_valid_folder(self, tmp_path: Path) -> None:
        config = ServerConfig(shared_folder=tmp_path, port=8000)
        assert config.shared_folder == tmp_path
        assert config.port == 8000

    def test_nonexistent_folder_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(ValueError, match="does not exist"):
            ServerConfig(shared_folder=nonexistent, port=8000)

    def test_file_instead_of_directory_raises(self, tmp_path: Path) -> None:
        file_path = tmp_path / "a_file.txt"
        file_path.write_text("content")
        with pytest.raises(ValueError, match="not a directory"):
            ServerConfig(shared_folder=file_path, port=8000)
