"""Tests for agent display functions."""

from pathlib import Path
from unittest.mock import patch


from agent.display import _resolve_lan_url


@patch("agent.display.detect_primary_lan_ip", return_value="192.168.1.42")
def test_resolve_lan_url_replaces_localhost(mock_ip) -> None:
    """_resolve_lan_url replaces localhost with LAN IP."""
    assert _resolve_lan_url("http://localhost:8001") == "http://192.168.1.42:8001"


@patch("agent.display.detect_primary_lan_ip", return_value="192.168.1.42")
def test_resolve_lan_url_replaces_127_0_0_1(mock_ip) -> None:
    """_resolve_lan_url replaces 127.0.0.1 with LAN IP."""
    assert _resolve_lan_url("http://127.0.0.1:8001") == "http://192.168.1.42:8001"


@patch("agent.display.detect_primary_lan_ip", return_value="192.168.1.42")
def test_resolve_lan_url_preserves_non_local_host(mock_ip) -> None:
    """_resolve_lan_url leaves non-local hostnames unchanged."""
    assert _resolve_lan_url("https://relay.example.com") == "https://relay.example.com"


@patch("agent.display.detect_primary_lan_ip", side_effect=RuntimeError("no network"))
def test_resolve_lan_url_returns_original_on_failure(mock_ip) -> None:
    """_resolve_lan_url returns original URL when LAN IP detection fails."""
    assert _resolve_lan_url("http://localhost:8001") == "http://localhost:8001"


@patch("agent.display.detect_primary_lan_ip", return_value="10.0.0.5")
def test_resolve_lan_url_preserves_scheme_and_path(mock_ip) -> None:
    """_resolve_lan_url preserves scheme, port, and path."""
    result = _resolve_lan_url("https://localhost:9000/some/path")
    assert result == "https://10.0.0.5:9000/some/path"


def test_print_mounted_outputs_mount_url(capsys) -> None:
    """print_mounted outputs the full mount URL."""
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="ABC12345",
        folder=Path("/home/user/files"),
        name="my-files",
    )
    captured = capsys.readouterr()
    assert "https://relay.example.com/m/ABC12345" in captured.out


def test_print_mounted_outputs_qr_code(capsys) -> None:
    """print_mounted outputs a QR code (ASCII art contains block characters or spaces)."""
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="ABC12345",
        folder=Path("/home/user/files"),
        name="my-files",
    )
    captured = capsys.readouterr()
    # QR codes use block characters — at minimum there are several lines
    lines = captured.out.splitlines()
    assert len(lines) >= 5  # QR code is at least a few lines tall


def test_print_mounted_qr_encodes_full_mount_url(capsys, monkeypatch) -> None:
    """print_mounted calls generate_ascii_qr with the full mount URL (non-local relay)."""
    from agent import display as display_module

    captured_urls = []

    def fake_qr(url: str) -> str:
        captured_urls.append(url)
        return "[QR]"

    monkeypatch.setattr(display_module, "generate_ascii_qr", fake_qr)
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="CODE1234",
        folder=Path("/tmp/share"),
        name="share",
    )
    assert len(captured_urls) == 1
    assert captured_urls[0] == "https://relay.example.com/m/CODE1234"


@patch("agent.display.detect_primary_lan_ip", return_value="192.168.1.10")
def test_print_mounted_qr_uses_lan_ip_for_localhost_relay(mock_ip, capsys, monkeypatch) -> None:
    """print_mounted QR code uses LAN IP when relay is localhost."""
    from agent import display as display_module

    captured_urls = []

    def fake_qr(url: str) -> str:
        captured_urls.append(url)
        return "[QR]"

    monkeypatch.setattr(display_module, "generate_ascii_qr", fake_qr)
    from agent.display import print_mounted
    print_mounted(
        relay_url="http://localhost:8001",
        code="LAN12345",
        folder=Path("/tmp/share"),
        name="share",
    )
    assert len(captured_urls) == 1
    assert captured_urls[0] == "http://192.168.1.10:8001/m/LAN12345"


def test_print_mounted_outputs_code(capsys) -> None:
    """print_mounted outputs the mount code."""
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="MYCODE99",
        folder=Path("/tmp/files"),
        name="files",
    )
    captured = capsys.readouterr()
    assert "MYCODE99" in captured.out


def test_print_mounted_outputs_folder(capsys) -> None:
    """print_mounted outputs the shared folder path."""
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="XXXX1234",
        folder=Path("/home/user/my-folder"),
        name="my-folder",
    )
    captured = capsys.readouterr()
    assert "/home/user/my-folder" in captured.out or "my-folder" in captured.out


def test_print_mounted_outputs_relay_url(capsys) -> None:
    """print_mounted outputs the relay URL."""
    from agent.display import print_mounted
    print_mounted(
        relay_url="https://relay.example.com",
        code="RLYTEST1",
        folder=Path("/tmp"),
        name="tmp",
    )
    captured = capsys.readouterr()
    assert "relay.example.com" in captured.out


def test_print_request_line_outputs_method_path_status(capsys) -> None:
    """print_request_line outputs 'METHOD /path STATUS' format."""
    from agent.display import print_request_line
    print_request_line(method="GET", path="/api/files", status=200)
    captured = capsys.readouterr()
    assert "GET" in captured.out
    assert "/api/files" in captured.out
    assert "200" in captured.out


def test_print_request_line_format(capsys) -> None:
    """print_request_line outputs on a single line."""
    from agent.display import print_request_line
    print_request_line(method="POST", path="/upload", status=201)
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1


def test_print_reconnect_status_outputs_attempt_and_delay(capsys) -> None:
    """print_reconnect_status outputs attempt number and delay."""
    from agent.display import print_reconnect_status
    print_reconnect_status(attempt=3, next_in_s=15.5)
    captured = capsys.readouterr()
    assert "3" in captured.out
    assert "15" in captured.out  # delay value (rounded or truncated is ok)


def test_print_connected_status_not_reconnected(capsys) -> None:
    """print_connected_status with reconnected=False outputs 'Connected'."""
    from agent.display import print_connected_status
    print_connected_status(reconnected=False)
    captured = capsys.readouterr()
    assert "Connected" in captured.out


def test_print_connected_status_reconnected(capsys) -> None:
    """print_connected_status with reconnected=True outputs reconnected indicator."""
    from agent.display import print_connected_status
    print_connected_status(reconnected=True)
    captured = capsys.readouterr()
    assert "reconnect" in captured.out.lower() or "Connected" in captured.out
