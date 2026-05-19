"""Terminal display functions for the agent CLI.

Prints mount status, request activity, and reconnection state to stdout.
Reuses generate_ascii_qr from server.app.services.qr_service.
"""

from pathlib import Path
from urllib.parse import urlparse, urlunparse

from server.app.services.network_service import detect_primary_lan_ip
from server.app.services.qr_service import generate_ascii_qr

# Hostnames that resolve to the local machine and won't work from other devices.
_LOCAL_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def _resolve_lan_url(url: str) -> str:
    """Replace localhost/127.0.0.1 in a URL with the LAN IP so other devices can reach it.

    If the host is already a non-local address, returns the URL unchanged.
    If LAN IP detection fails, returns the URL unchanged (caller can still
    use it locally).

    Args:
        url: URL that may contain a local-only hostname.

    Returns:
        URL with the hostname replaced by the LAN IP, or the original URL on failure.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None or hostname not in _LOCAL_HOSTS:
        return url
    try:
        lan_ip = detect_primary_lan_ip()
    except RuntimeError:
        return url
    # Replace hostname but preserve port
    new_netloc = f"{lan_ip}:{parsed.port}" if parsed.port else lan_ip
    return urlunparse(parsed._replace(netloc=new_netloc))


def _build_mount_url(relay_url: str, code: str) -> str:
    """Construct the full public mount URL from relay base URL and mount code.

    Args:
        relay_url: Base URL of the relay server (e.g. 'https://relay.example.com').
        code:      8-character mount code assigned by the relay.

    Returns:
        Full mount URL (e.g. 'https://relay.example.com/m/ABC12345').
    """
    return f"{relay_url.rstrip('/')}/m/{code}"


def print_mounted(relay_url: str, code: str, folder: Path, name: str) -> None:
    """Print mount status to stdout after a successful relay registration.

    Displays:
    - ASCII QR code for the mount URL
    - Mount URL
    - Mount code
    - Shared folder path
    - Relay URL

    Args:
        relay_url: Base URL of the relay server.
        code:      Mount code assigned by the relay.
        folder:    Local folder being shared.
        name:      Human-readable name for the mount.
    """
    mount_url = _build_mount_url(relay_url, code)
    lan_mount_url = _build_mount_url(_resolve_lan_url(relay_url), code)
    qr = generate_ascii_qr(lan_mount_url)
    print(qr)
    print(f"Mount URL:  {lan_mount_url}")
    if lan_mount_url != mount_url:
        print(f"Local URL:  {mount_url}")
    print(f"Code:       {code}")
    print(f"Folder:     {folder}")
    print(f"Relay:      {relay_url}")
    print(f"Name:       {name}")


def print_request_line(method: str, path: str, status: int) -> None:
    """Print a single-line request activity indicator.

    Format: 'METHOD /path STATUS'

    Args:
        method: HTTP method (e.g. 'GET', 'POST').
        path:   Request path (e.g. '/api/files').
        status: HTTP status code (e.g. 200).
    """
    print(f"{method} {path} {status}")


def print_reconnect_status(attempt: int, next_in_s: float) -> None:
    """Print reconnection status with attempt number and next retry delay.

    Args:
        attempt:   Current reconnect attempt number (1-based).
        next_in_s: Seconds until the next retry attempt.
    """
    print(f"Reconnecting (attempt {attempt}, next in {next_in_s:.1f}s)...")


def print_connected_status(reconnected: bool) -> None:
    """Print connection status line.

    Args:
        reconnected: True if this is a reconnect (not initial connect).
    """
    if reconnected:
        print("Connected (reconnected)")
    else:
        print("Connected")
