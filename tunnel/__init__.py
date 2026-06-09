"""Tunnel protocol package.

Public API re-exports — importers may use either:
    from tunnel import serialize_frame, FrameType, TunnelConnection, ...
    from tunnel.frames import serialize_frame
"""

from tunnel.connection import StreamState, TunnelConnection
from tunnel.constants import (
    FIRST_BYTE_TIMEOUT_S,
    HEADER_FORMAT,
    HEADER_SIZE,
    HEARTBEAT_INTERVAL_S,
    HEARTBEAT_MISSED_LIMIT,
    MAX_PAYLOAD_BYTES,
    MAX_STREAMS,
    QUEUE_DEPTH,
)
from tunnel.enums import FrameType
from tunnel.exceptions import (
    FirstByteTimeoutError,
    FrameTooLargeError,
    StreamLimitError,
    StreamNotFoundError,
    TunnelError,
)
from tunnel.frames import deserialize_frame, serialize_frame
from tunnel.protocol import WebSocketProtocol
from tunnel.ws_payload import (
    WsMessageKind,
    decode_ws_message,
    encode_binary_message,
    encode_text_message,
)

__all__ = [
    # High-level connection
    "StreamState",
    "TunnelConnection",
    # Constants
    "FIRST_BYTE_TIMEOUT_S",
    "HEADER_FORMAT",
    "HEADER_SIZE",
    "HEARTBEAT_INTERVAL_S",
    "HEARTBEAT_MISSED_LIMIT",
    "MAX_PAYLOAD_BYTES",
    "MAX_STREAMS",
    "QUEUE_DEPTH",
    # Enums
    "FrameType",
    # Exceptions
    "FirstByteTimeoutError",
    "FrameTooLargeError",
    "StreamLimitError",
    "StreamNotFoundError",
    "TunnelError",
    # Frame functions
    "deserialize_frame",
    "serialize_frame",
    # Protocol interface
    "WebSocketProtocol",
    # WS payload codec
    "WsMessageKind",
    "decode_ws_message",
    "encode_binary_message",
    "encode_text_message",
]
