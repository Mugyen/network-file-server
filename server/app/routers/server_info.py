"""Server info API router.

Provides GET /api/server-info with IP, port, URL, QR code, and mode data.
"""

import logging
import socket

from fastapi import APIRouter

from server.app.config import get_server_config
from server.app.models.schemas import ServerInfo
from server.app.services.network_service import detect_all_lan_ips, detect_primary_lan_ip
from server.app.services.qr_service import generate_svg_qr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["server-info"])


@router.get("/server-info", response_model=ServerInfo)
def get_server_info() -> ServerInfo:
    """Return server information including IP, port, URL, and SVG QR code.

    Detects primary and all LAN IPs, constructs the server URL,
    and generates an SVG QR code encoding that URL.

    If network detection fails, returns ip="unknown", url="unknown",
    empty qr_svg, and empty all_ips list.
    """
    config = get_server_config()
    port = config.port

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
        )

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
    )
