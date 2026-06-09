"""Tests for network service.

Tests LAN IP detection functions. These run against the real network stack.
"""

import re

from shared.network import detect_all_lan_ips, detect_primary_lan_ip

# IPv4 pattern: 1-3 digits . 1-3 digits . 1-3 digits . 1-3 digits
IPV4_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


class TestDetectPrimaryLanIp:
    """Tests for detect_primary_lan_ip function."""

    def test_returns_valid_ipv4(self) -> None:
        """Must return a string matching IPv4 format."""
        ip = detect_primary_lan_ip()
        assert isinstance(ip, str)
        assert IPV4_PATTERN.match(ip), f"'{ip}' does not match IPv4 pattern"

    def test_not_loopback(self) -> None:
        """Primary LAN IP must not be a loopback address."""
        ip = detect_primary_lan_ip()
        assert not ip.startswith("127."), f"Got loopback address: {ip}"


class TestDetectAllLanIps:
    """Tests for detect_all_lan_ips function."""

    def test_returns_non_empty_list(self) -> None:
        """Must return a non-empty list."""
        ips = detect_all_lan_ips()
        assert isinstance(ips, list)
        assert len(ips) > 0

    def test_all_entries_are_valid_ipv4(self) -> None:
        """Every entry must be a valid IPv4 string."""
        ips = detect_all_lan_ips()
        for ip in ips:
            assert isinstance(ip, str)
            assert IPV4_PATTERN.match(ip), f"'{ip}' does not match IPv4 pattern"

    def test_no_loopback_addresses(self) -> None:
        """No entry should be a loopback address."""
        ips = detect_all_lan_ips()
        for ip in ips:
            assert not ip.startswith("127."), f"Got loopback address: {ip}"

    def test_primary_ip_in_all_ips(self) -> None:
        """The primary LAN IP should appear in the all-IPs list."""
        primary = detect_primary_lan_ip()
        all_ips = detect_all_lan_ips()
        assert primary in all_ips, f"Primary IP {primary} not found in {all_ips}"
