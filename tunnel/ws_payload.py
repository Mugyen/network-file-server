"""WS_DATA payload codec — preserves text-vs-binary frame kind across the tunnel.

WebSocket messages have a frame kind (text or binary) that must survive the
trip through the tunnel's WS_DATA frames (which carry raw bytes). Each WS_DATA
payload is prefixed with a single marker byte so the far side can reconstruct
the original frame kind:

    0x00 = text   (remaining bytes are UTF-8)
    0x01 = binary (remaining bytes are the message verbatim)

Both the relay (browser side) and the agent (local-app side) use this codec,
so the convention lives here in the tunnel package they share.
"""

from enum import Enum

from tunnel.exceptions import TunnelError


class WsMessageKind(Enum):
    """Frame kind of a bridged WebSocket message."""

    TEXT = 0x00
    BINARY = 0x01


def encode_text_message(text: str) -> bytes:
    """Encode a text WebSocket message for transport in a WS_DATA frame."""
    if not isinstance(text, str):
        raise ValueError(f"text message must be str, got {type(text)!r}")
    return bytes([WsMessageKind.TEXT.value]) + text.encode("utf-8")


def encode_binary_message(data: bytes) -> bytes:
    """Encode a binary WebSocket message for transport in a WS_DATA frame."""
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError(f"binary message must be bytes, got {type(data)!r}")
    return bytes([WsMessageKind.BINARY.value]) + bytes(data)


def decode_ws_message(payload: bytes) -> tuple[WsMessageKind, bytes]:
    """Decode a WS_DATA payload back into (kind, message bytes).

    Raises:
        TunnelError: On an empty payload or unknown kind marker — both mean
                     the two tunnel endpoints disagree on the wire format.
    """
    if len(payload) == 0:
        raise TunnelError("WS_DATA payload is empty — missing kind marker")
    marker = payload[0]
    try:
        kind = WsMessageKind(marker)
    except ValueError as exc:
        # Convert the enum lookup failure into the tunnel's domain exception.
        raise TunnelError(f"Unknown WS message kind marker: {marker:#x}") from exc
    return kind, payload[1:]
