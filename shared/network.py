"""Network service for LAN IP address detection.

Provides functions to detect the primary LAN IP and all non-loopback IPv4 addresses.
"""

import socket

import ifaddr


def detect_primary_lan_ip() -> str:
    """Detect the primary LAN IP address using the UDP socket trick.

    Opens a UDP socket to a public DNS server (8.8.8.8:80) without sending data,
    then reads the local socket address. This reliably returns the interface IP
    that the OS would use for outbound traffic.

    Returns:
        IPv4 address string (e.g. "192.168.1.5").

    Raises:
        RuntimeError: If no network connection is available.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip: str = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError as exc:
        raise RuntimeError(
            "Cannot detect LAN IP address: no network connection available"
        ) from exc


def detect_all_lan_ips() -> list[str]:
    """Detect all non-loopback IPv4 addresses on the machine.

    Uses the ifaddr library to enumerate network adapters and their addresses.
    Filters out loopback (127.x.x.x) and non-IPv4 addresses.

    Returns:
        Non-empty list of IPv4 address strings.

    Raises:
        RuntimeError: If no non-loopback IPv4 addresses are found.
    """
    adapters = ifaddr.get_adapters()
    ips: list[str] = []

    for adapter in adapters:
        for ip_info in adapter.ips:
            # ifaddr returns str for IPv4 and tuple for IPv6
            if isinstance(ip_info.ip, str) and not ip_info.ip.startswith("127."):
                ips.append(ip_info.ip)

    if not ips:
        raise RuntimeError(
            "No non-loopback IPv4 addresses found on any network adapter"
        )

    return ips
