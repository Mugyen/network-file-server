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


class TestRunWithDefaults:
    """Tests for run_with_defaults convenience function."""

    def test_signature_has_one_parameter(self) -> None:
        """run_with_defaults must accept exactly one parameter: folder (str)."""
        sig = inspect.signature(run_with_defaults)
        params = list(sig.parameters.values())
        assert len(params) == 1
        assert params[0].name == "folder"
        assert params[0].annotation == str
