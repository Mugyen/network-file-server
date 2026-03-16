"""Enum types for the tunnel protocol."""

from enum import Enum


class FrameType(int, Enum):
    """Binary frame type byte values for the tunnel wire protocol."""

    OPEN = 0x01
    DATA = 0x02
    CLOSE = 0x03
    CANCEL = 0x04
    ERROR = 0x05
    PING = 0x06
    PONG = 0x07
    WS_OPEN = 0x08
    WS_DATA = 0x09
    WS_CLOSE = 0x0A
