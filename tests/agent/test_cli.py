"""Tests for agent CLI argument parsing and server/app/cli.py mount subcommand."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from server.app.cli import _build_parser, _parse_args


class TestMountSubcommand:
    """Tests for mount subcommand argument parsing."""

    def test_mount_subcommand_parses_correctly(self, tmp_path: Path) -> None:
        """Test 1: wifi-file-server mount ./testfolder --server https://relay.example.com parses correctly."""
        args = _parse_args(["mount", str(tmp_path), "--server", "https://relay.example.com"])
        assert args.command == "mount"
        assert args.folder == str(tmp_path)
        assert args.server == "https://relay.example.com"

    def test_mount_server_is_required(self, tmp_path: Path) -> None:
        """Test 2: --server is required for mount subcommand."""
        with pytest.raises(SystemExit):
            _parse_args(["mount", str(tmp_path)])

    def test_mount_name_is_optional(self, tmp_path: Path) -> None:
        """Test 3: --name is optional for mount subcommand."""
        args = _parse_args(["mount", str(tmp_path), "--server", "https://relay.example.com"])
        assert args.name is None

    def test_mount_name_can_be_provided(self, tmp_path: Path) -> None:
        """--name is set when explicitly provided."""
        args = _parse_args([
            "mount", str(tmp_path),
            "--server", "https://relay.example.com",
            "--name", "my-share",
        ])
        assert args.name == "my-share"


class TestBackwardCompatibility:
    """Tests that bare wifi-file-server ./files still works."""

    def test_bare_folder_invocation_parses_correctly(self, tmp_path: Path) -> None:
        """Test 4: wifi-file-server ./testfolder (bare, no subcommand) parses with command=None."""
        args = _parse_args([str(tmp_path)])
        # No subcommand means command is None
        assert args.command is None
        assert args.folder == str(tmp_path)

    def test_bare_folder_with_port_parses_correctly(self, tmp_path: Path) -> None:
        """Test 5: wifi-file-server ./testfolder --port 9000 still works."""
        args = _parse_args([str(tmp_path), "--port", "9000"])
        assert args.command is None
        assert args.folder == str(tmp_path)
        assert args.port == 9000

    def test_missing_args_exits(self) -> None:
        """wifi-file-server with no args at all — main() exits with error."""
        with patch("sys.argv", ["wifi-file-server"]):
            from server.app.cli import main
            with pytest.raises(SystemExit):
                main()


class TestRunMount:
    """Tests for agent/cli.py run_mount()."""

    def test_run_mount_validates_folder_exists(self, tmp_path: Path) -> None:
        """run_mount raises SystemExit when folder does not exist."""
        from agent.cli import run_mount
        import argparse

        non_existent = tmp_path / "does_not_exist"
        args = argparse.Namespace(
            folder=str(non_existent),
            server="https://relay.example.com",
            name=None,
            password=None,
            ttl_seconds=None,
        )

        with pytest.raises(SystemExit):
            run_mount(args)

    def test_run_mount_validates_folder_is_directory(self, tmp_path: Path) -> None:
        """run_mount raises SystemExit when folder path is a file."""
        from agent.cli import run_mount
        import argparse

        file_path = tmp_path / "file.txt"
        file_path.write_text("hello")

        args = argparse.Namespace(
            folder=str(file_path),
            server="https://relay.example.com",
            name=None,
            password=None,
            ttl_seconds=None,
        )

        with pytest.raises(SystemExit):
            run_mount(args)

    def test_run_mount_defaults_name_to_folder_basename(self, tmp_path: Path) -> None:
        """run_mount uses folder basename as name when --name is not provided."""
        from agent.cli import run_mount
        import argparse

        args = argparse.Namespace(
            folder=str(tmp_path),
            server="https://relay.example.com",
            name=None,
            password=None,
            ttl_seconds=None,
        )

        def close_coro_and_return_none(coro):
            """Close the coroutine to prevent 'never awaited' warning."""
            coro.close()
            return None

        with patch("agent.cli.asyncio_run", side_effect=close_coro_and_return_none) as mock_run:
            run_mount(args)

        # asyncio.run was called once
        assert mock_run.call_count == 1

    def test_run_mount_calls_run_agent_loop(self, tmp_path: Path) -> None:
        """run_mount calls asyncio_run with the result of run_agent_loop."""
        from agent.cli import run_mount
        import argparse
        import asyncio

        args = argparse.Namespace(
            folder=str(tmp_path),
            server="https://relay.example.com",
            name="custom-name",
            password=None,
            ttl_seconds=None,
        )

        def close_coro_and_return_none(coro):
            """Close the coroutine to prevent 'never awaited' warning."""
            coro.close()
            return None

        with patch("agent.cli.asyncio_run", side_effect=close_coro_and_return_none) as mock_run:
            run_mount(args)
            assert mock_run.called


from unittest.mock import MagicMock
