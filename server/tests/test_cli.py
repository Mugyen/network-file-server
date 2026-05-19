import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from server.app.cli import _build_parser, run_with_defaults


class TestArgParsing:
    """Tests for CLI argument parsing."""

    def test_parses_folder_argument(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.folder == "/tmp/shared"

    def test_parses_port_argument(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "--port", "9000"])
        assert args.port == 9000

    def test_parses_short_port_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "-p", "9000"])
        assert args.port == 9000

    def test_parses_host_argument(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "--host", "127.0.0.1"])
        assert args.host == "127.0.0.1"

    def test_parses_all_arguments(self) -> None:
        parser = _build_parser()
        args = parser.parse_args([
            "/tmp/shared", "--port", "9000", "--host", "127.0.0.1"
        ])
        assert args.folder == "/tmp/shared"
        assert args.port == 9000
        assert args.host == "127.0.0.1"

    def test_missing_folder_raises_system_exit(self) -> None:
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_port_defaults_to_none(self) -> None:
        """Port is None when not provided (defaults applied in main())."""
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.port is None

    def test_host_defaults_to_none(self) -> None:
        """Host is None when not provided (defaults applied in main())."""
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.host is None

    def test_parses_password_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "--password", "mysecret"])
        assert args.password == "mysecret"

    def test_password_defaults_to_none(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.password is None

    def test_parses_read_only_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "--read-only"])
        assert args.read_only is True

    def test_read_only_defaults_to_false(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.read_only is False

    def test_parses_receive_flag(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared", "--receive"])
        assert args.receive is True

    def test_receive_defaults_to_false(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["/tmp/shared"])
        assert args.receive is False


class TestCLIValidation:
    """Tests for CLI argument validation logic in main()."""

    def test_read_only_and_receive_together_exits(self, tmp_path: Path) -> None:
        """--read-only and --receive together should cause SystemExit."""
        with patch.object(
            sys,
            "argv",
            ["network-file-server", str(tmp_path), "--read-only", "--receive"],
        ):
            from server.app.cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_password_over_72_bytes_exits(self, tmp_path: Path) -> None:
        """--password with >72 byte value should cause SystemExit."""
        long_password = "a" * 73
        with patch.object(
            sys,
            "argv",
            ["network-file-server", str(tmp_path), "--password", long_password],
        ):
            from server.app.cli import main

            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestRunWithDefaults:
    """Tests for run_with_defaults convenience function."""

    def test_signature_has_one_parameter(self) -> None:
        """run_with_defaults must accept exactly one parameter: folder (str)."""
        sig = inspect.signature(run_with_defaults)
        params = list(sig.parameters.values())
        assert len(params) == 1
        assert params[0].name == "folder"
        assert params[0].annotation == str
