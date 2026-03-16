"""Tests for Task 2 — --password and --ttl flags in mount parser."""

import argparse
import pytest

from server.app.cli import _build_mount_parser, _parse_args


class TestMountParserPasswordTTLFlags:
    """Tests for --password and --ttl flags added to mount subcommand."""

    def test_password_flag_is_accepted(self, tmp_path) -> None:
        """_parse_args(["mount", ".", "--server", "x", "--password", "secret"]) has password="secret"."""
        args = _parse_args(
            ["mount", str(tmp_path), "--server", "http://x", "--password", "secret"]
        )
        assert args.password == "secret"

    def test_ttl_flag_converts_to_seconds(self, tmp_path) -> None:
        """_parse_args(["mount", ".", "--server", "x", "--ttl", "30m"]) has ttl_seconds=1800."""
        args = _parse_args(
            ["mount", str(tmp_path), "--server", "http://x", "--ttl", "30m"]
        )
        assert args.ttl_seconds == 1800

    def test_ttl_flag_hours(self, tmp_path) -> None:
        """--ttl 2h results in ttl_seconds=7200."""
        args = _parse_args(
            ["mount", str(tmp_path), "--server", "http://x", "--ttl", "2h"]
        )
        assert args.ttl_seconds == 7200

    def test_ttl_flag_invalid_value_exits(self, tmp_path) -> None:
        """_parse_args(["mount", ".", "--server", "x", "--ttl", "bad"]) exits with error."""
        with pytest.raises(SystemExit):
            _parse_args(
                ["mount", str(tmp_path), "--server", "http://x", "--ttl", "bad"]
            )

    def test_password_default_is_none(self, tmp_path) -> None:
        """password is None when --password not provided."""
        args = _parse_args(["mount", str(tmp_path), "--server", "http://x"])
        assert args.password is None

    def test_ttl_default_is_none(self, tmp_path) -> None:
        """ttl_seconds is None when --ttl not provided."""
        args = _parse_args(["mount", str(tmp_path), "--server", "http://x"])
        assert args.ttl_seconds is None
