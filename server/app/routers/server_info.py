"""Server info API router.

Provides GET /api/server-info with IP, port, URL, QR code, and mode data.
In remote mount mode, returns the relay mount URL instead of local LAN URL.
"""

import logging
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Request

from server.app.config import get_server_config
from server.app.models.schemas import ServerInfo
from server.app.services.network_service import detect_all_lan_ips, detect_primary_lan_ip
from server.app.services.qr_service import generate_svg_qr
from server.app.services.relay_identity import trusted_role, trusted_user

logger = logging.getLogger(__name__)

# Hostnames that resolve to the local machine and won't work from other devices.
_LOCAL_HOSTS: frozenset[str] = frozenset({"localhost", "127.0.0.1", "::1"})

router = APIRouter(prefix="/api", tags=["server-info"])


def _build_mount_url(relay_url: str, mount_code: str, lan_ip: str) -> str:
    """Build the mount URL, replacing localhost with LAN IP for device access.

    Args:
        relay_url:  Base URL of the relay server.
        mount_code: Mount code assigned by the relay.
        lan_ip:     LAN IP to substitute for local-only hostnames.

    Returns:
        Full mount URL with LAN-accessible hostname.
    """
    parsed = urlparse(relay_url)
    hostname = parsed.hostname
    if hostname is not None and hostname in _LOCAL_HOSTS:
        new_netloc = f"{lan_ip}:{parsed.port}" if parsed.port else lan_ip
        relay_url = parsed._replace(netloc=new_netloc).geturl()
    return f"{relay_url.rstrip('/')}/m/{mount_code}"


@router.get("/server-info", response_model=ServerInfo)
def get_server_info(request: Request) -> ServerInfo:
    """Return server information including IP, port, URL, and SVG QR code.

    In remote mount mode (mount_code set), returns the relay mount URL
    instead of local http://ip:port. This ensures the QR code shown in
    the client points to the correct relay URL.

    If network detection fails, returns ip="unknown", url="unknown",
    empty qr_svg, and empty all_ips list.
    """
    config = get_server_config()
    port = config.port

    role = trusted_role(request.headers)
    current_role = role.value if role is not None else None
    current_user = trusted_user(request.headers)
    access_mode = (
        request.headers.get("x-wfs-access-mode")
        if current_user is not None or current_role is not None
        else None
    )

    try:
        ip = detect_primary_lan_ip()
        all_ips = detect_all_lan_ips()
    except RuntimeError as exc:
        logger.warning("Network detection failed: %s", exc)
        return ServerInfo(
            ip="unknown",
            port=port,
            url="unknown",
            qr_svg="",
            all_ips=[],
            read_only=config.read_only,
            receive=config.receive,
            password_required=config.password_hash is not None,
            hostname=socket.gethostname(),
            current_user=current_user,
            current_role=current_role,
            access_mode=access_mode,
        )

    # Remote mount mode: show relay mount URL instead of local server URL
    if config.mount_code is not None and config.relay_url is not None:
        url = _build_mount_url(config.relay_url, config.mount_code, ip)
        relay_parsed = urlparse(config.relay_url)
        relay_host = relay_parsed.hostname
        if relay_host is not None and relay_host in _LOCAL_HOSTS:
            port = relay_parsed.port if relay_parsed.port else 80
        else:
            port = relay_parsed.port if relay_parsed.port else 443
    else:
        url = f"http://{ip}:{port}"

    qr_svg = generate_svg_qr(url)

    return ServerInfo(
        ip=ip,
        port=port,
        url=url,
        qr_svg=qr_svg,
        all_ips=all_ips,
        read_only=config.read_only,
        receive=config.receive,
        password_required=config.password_hash is not None,
        hostname=socket.gethostname(),
        current_user=current_user,
        current_role=current_role,
        access_mode=access_mode,
    )
