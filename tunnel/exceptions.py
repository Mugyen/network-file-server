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
