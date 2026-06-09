"""QR code generation service.

Provides ASCII QR codes for terminal display and SVG QR codes for web embedding.
"""

import io

import qrcode
import qrcode.image.svg


def generate_ascii_qr(url: str) -> str:
    """Generate an ASCII QR code string from a URL.

    Uses qrcode library to produce a text-based QR code suitable for terminal display.

    Args:
        url: The URL to encode. Must be non-empty.

    Returns:
        Multi-line ASCII string representing the QR code.

    Raises:
        ValueError: If url is empty.
    """
    if not url:
        raise ValueError("url must not be empty")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)

    buffer = io.StringIO()
    qr.print_ascii(out=buffer)
    return buffer.getvalue()


def generate_svg_qr(url: str) -> str:
    """Generate an SVG QR code string from a URL.

    Uses qrcode library with SvgPathImage factory to produce an SVG string.

    Args:
        url: The URL to encode. Must be non-empty.

    Returns:
        UTF-8 string containing the SVG markup for the QR code.

    Raises:
        ValueError: If url is empty.
    """
    if not url:
        raise ValueError("url must not be empty")

    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
    buffer = io.BytesIO()
    img.save(buffer)
    return buffer.getvalue().decode("utf-8")
