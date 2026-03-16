"""Binary frame serialization and deserialization for the tunnel protocol."""

import struct
import uuid

from tunnel.constants import HEADER_FORMAT, HEADER_SIZE, MAX_PAYLOAD_BYTES
from tunnel.enums import FrameType
from tunnel.exceptions import FrameTooLargeError, TunnelError


def serialize_frame(frame_type: FrameType, request_id: uuid.UUID, payload: bytes) -> bytes:
    """Pack a tunnel frame into its wire representation.

    The wire format is: 1-byte frame type | 16-byte UUID | 4-byte payload length | payload.

    Args:
        frame_type: The FrameType value for this frame.
        request_id: UUID that correlates this frame to a specific stream.
        payload:    Binary payload for the frame (may be empty).

    Returns:
        Packed bytes ready to send over the WebSocket connection.

    Raises:
        FrameTooLargeError: When len(payload) exceeds MAX_PAYLOAD_BYTES.
    """
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise FrameTooLargeError(
            f"Payload size {len(payload)} exceeds maximum {MAX_PAYLOAD_BYTES} bytes"
        )
    header = struct.pack(HEADER_FORMAT, int(frame_type), request_id.bytes, len(payload))
    return header + payload


def deserialize_frame(data: bytes) -> tuple[FrameType, uuid.UUID, bytes]:
    """Unpack a tunnel frame from its wire representation.

    Args:
        data: Raw bytes received from the WebSocket connection.

    Returns:
        A tuple of (frame_type, request_id, payload).

    Raises:
        TunnelError:  When data is shorter than HEADER_SIZE, or when the
                      declared payload length does not match actual data length.
        ValueError:   When the frame type byte is not a valid FrameType value.
    """
    if len(data) < HEADER_SIZE:
        raise TunnelError(
            f"Frame too short: expected at least {HEADER_SIZE} bytes, got {len(data)}"
        )

    type_byte, uuid_bytes, payload_length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])

    # Raises ValueError for unknown type byte — let it propagate as-is.
    frame_type = FrameType(type_byte)

    actual_payload = data[HEADER_SIZE:]
    if len(actual_payload) != payload_length:
        raise TunnelError(
            f"Payload length mismatch: header declares {payload_length} bytes, "
            f"got {len(actual_payload)} bytes"
        )

    request_id = uuid.UUID(bytes=uuid_bytes)
    return frame_type, request_id, actual_payload
