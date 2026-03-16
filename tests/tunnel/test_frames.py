"""Tests for tunnel binary frame serialization and deserialization."""

import uuid

import pytest

from tunnel.constants import HEADER_SIZE, MAX_PAYLOAD_BYTES
from tunnel.enums import FrameType
from tunnel.exceptions import FrameTooLargeError, TunnelError
from tunnel.frames import deserialize_frame, serialize_frame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _round_trip(
    frame_type: FrameType,
    request_id: uuid.UUID,
    payload: bytes,
) -> tuple[FrameType, uuid.UUID, bytes]:
    """Serialize then immediately deserialize a frame and return the result."""
    raw = serialize_frame(frame_type, request_id, payload)
    return deserialize_frame(raw)


# ---------------------------------------------------------------------------
# HEADER_SIZE constant
# ---------------------------------------------------------------------------

def test_header_size_is_21() -> None:
    assert HEADER_SIZE == 21


# ---------------------------------------------------------------------------
# MAX_PAYLOAD_BYTES constant
# ---------------------------------------------------------------------------

def test_max_payload_bytes_is_64kb() -> None:
    assert MAX_PAYLOAD_BYTES == 65536


# ---------------------------------------------------------------------------
# FrameType enum values
# ---------------------------------------------------------------------------

def test_frame_type_sequential_hex_values() -> None:
    assert FrameType.OPEN == 0x01
    assert FrameType.DATA == 0x02
    assert FrameType.CLOSE == 0x03
    assert FrameType.CANCEL == 0x04
    assert FrameType.ERROR == 0x05
    assert FrameType.PING == 0x06
    assert FrameType.PONG == 0x07


def test_frame_type_has_seven_members() -> None:
    # WS_OPEN, WS_DATA, WS_CLOSE have been added — now 10 total
    assert len(FrameType) == 10


# ---------------------------------------------------------------------------
# WS FrameType values (0x08, 0x09, 0x0A)
# ---------------------------------------------------------------------------

def test_ws_frame_type_values() -> None:
    assert FrameType.WS_OPEN == 0x08
    assert FrameType.WS_DATA == 0x09
    assert FrameType.WS_CLOSE == 0x0A


def test_frame_type_has_ten_members_after_ws_types() -> None:
    # Verifies WS_OPEN, WS_DATA, WS_CLOSE were added (7 original + 3 WS = 10)
    assert len(FrameType) == 10


def test_ws_open_round_trip() -> None:
    rid = uuid.uuid4()
    payload = b'{"path": "/ws", "query": ""}'
    ft, returned_id, returned_payload = _round_trip(FrameType.WS_OPEN, rid, payload)
    assert ft == FrameType.WS_OPEN
    assert returned_id == rid
    assert returned_payload == payload


def test_ws_data_round_trip() -> None:
    rid = uuid.uuid4()
    payload = b"some websocket message"
    ft, returned_id, returned_payload = _round_trip(FrameType.WS_DATA, rid, payload)
    assert ft == FrameType.WS_DATA
    assert returned_id == rid
    assert returned_payload == payload


def test_ws_close_round_trip_empty_payload() -> None:
    rid = uuid.uuid4()
    ft, returned_id, returned_payload = _round_trip(FrameType.WS_CLOSE, rid, b"")
    assert ft == FrameType.WS_CLOSE
    assert returned_id == rid
    assert returned_payload == b""


# ---------------------------------------------------------------------------
# serialize_frame output length
# ---------------------------------------------------------------------------

def test_serialize_data_frame_length() -> None:
    rid = uuid.uuid4()
    raw = serialize_frame(FrameType.DATA, rid, b"hello")
    assert len(raw) == HEADER_SIZE + len(b"hello")


def test_serialize_empty_payload_length() -> None:
    rid = uuid.uuid4()
    raw = serialize_frame(FrameType.PING, rid, b"")
    assert len(raw) == HEADER_SIZE


# ---------------------------------------------------------------------------
# Round-trip for all 7 FrameType values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("frame_type", list(FrameType))
def test_round_trip_all_frame_types(frame_type: FrameType) -> None:
    rid = uuid.uuid4()
    payload = b"payload_data"
    ft, returned_id, returned_payload = _round_trip(frame_type, rid, payload)
    assert ft == frame_type
    assert returned_id == rid
    assert returned_payload == payload


# ---------------------------------------------------------------------------
# UUID byte preservation
# ---------------------------------------------------------------------------

def test_uuid_preserved_through_round_trip() -> None:
    rid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    _, returned_id, _ = _round_trip(FrameType.DATA, rid, b"check")
    assert returned_id == rid
    assert returned_id.bytes == rid.bytes


def test_uuid_bytes_big_endian_in_header() -> None:
    rid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    raw = serialize_frame(FrameType.DATA, rid, b"")
    # Bytes 1..17 (inclusive) are the UUID — check exact bytes
    assert raw[1:17] == rid.bytes


# ---------------------------------------------------------------------------
# Empty payload round-trip
# ---------------------------------------------------------------------------

def test_round_trip_empty_payload() -> None:
    rid = uuid.uuid4()
    ft, returned_id, payload = _round_trip(FrameType.CLOSE, rid, b"")
    assert ft == FrameType.CLOSE
    assert returned_id == rid
    assert payload == b""


# ---------------------------------------------------------------------------
# Oversized payload rejection
# ---------------------------------------------------------------------------

def test_serialize_oversized_payload_raises_frame_too_large() -> None:
    rid = uuid.uuid4()
    with pytest.raises(FrameTooLargeError):
        serialize_frame(FrameType.DATA, rid, b"x" * (MAX_PAYLOAD_BYTES + 1))


def test_serialize_exactly_max_payload_does_not_raise() -> None:
    rid = uuid.uuid4()
    raw = serialize_frame(FrameType.DATA, rid, b"x" * MAX_PAYLOAD_BYTES)
    assert len(raw) == HEADER_SIZE + MAX_PAYLOAD_BYTES


# ---------------------------------------------------------------------------
# Undersized input rejection
# ---------------------------------------------------------------------------

def test_deserialize_too_short_raises_tunnel_error() -> None:
    with pytest.raises(TunnelError):
        deserialize_frame(b"short")


def test_deserialize_exactly_20_bytes_raises_tunnel_error() -> None:
    # One byte short of a valid header
    with pytest.raises(TunnelError):
        deserialize_frame(b"\x01" * 20)


# ---------------------------------------------------------------------------
# Payload length mismatch rejection
# ---------------------------------------------------------------------------

def test_deserialize_payload_length_mismatch_raises_tunnel_error() -> None:
    rid = uuid.uuid4()
    raw = serialize_frame(FrameType.DATA, rid, b"hello")
    # Truncate the payload so actual length < header-declared length
    truncated = raw[:-1]
    with pytest.raises(TunnelError):
        deserialize_frame(truncated)


# ---------------------------------------------------------------------------
# Invalid frame type byte rejection
# ---------------------------------------------------------------------------

def test_deserialize_invalid_frame_type_raises_value_error() -> None:
    rid = uuid.uuid4()
    raw = bytearray(serialize_frame(FrameType.DATA, rid, b""))
    raw[0] = 0xFF  # 0xFF is not a valid FrameType
    with pytest.raises(ValueError):
        deserialize_frame(bytes(raw))
