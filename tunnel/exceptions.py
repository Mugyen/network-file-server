"""Typed exception hierarchy for the tunnel protocol."""


class TunnelError(Exception):
    """Base exception for all tunnel protocol errors."""


class FrameTooLargeError(TunnelError):
    """Raised when a frame payload exceeds MAX_PAYLOAD_BYTES."""


class StreamLimitError(TunnelError):
    """Raised when opening a stream would exceed MAX_STREAMS."""


class FirstByteTimeoutError(TunnelError):
    """Raised when a stream does not produce its first byte within FIRST_BYTE_TIMEOUT_S."""


class StreamNotFoundError(TunnelError):
    """Raised when a frame references an unknown or closed stream UUID."""


class MetadataError(TunnelError):
    """Raised when OPEN/WS_OPEN metadata is malformed or missing fields."""


class MetadataTooLargeError(MetadataError):
    """Raised when serialized metadata exceeds METADATA_MAX_BYTES."""


class TunnelSendError(TunnelError):
    """Raised when sending a frame over the transport fails.

    Wraps transport-level errors (closed socket, broken pipe) so callers
    can convert a mid-request send failure into a clean error response
    instead of an unhandled exception.
    """
