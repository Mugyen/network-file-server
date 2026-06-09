"""Tests for the WS_DATA payload codec (tunnel.ws_payload)."""

import pytest

from tunnel.exceptions import TunnelError
from tunnel.ws_payload import (
    WsMessageKind,
    decode_ws_message,
    encode_binary_message,
    encode_text_message,
)


class TestEncodeText:
    def test_round_trip(self) -> None:
        kind, data = decode_ws_message(encode_text_message("hello"))
        assert kind is WsMessageKind.TEXT
        assert data == b"hello"

    def test_empty_string_round_trips(self) -> None:
        kind, data = decode_ws_message(encode_text_message(""))
        assert kind is WsMessageKind.TEXT
        assert data == b""

    def test_unicode_round_trips(self) -> None:
        kind, data = decode_ws_message(encode_text_message("héllo ☃"))
        assert kind is WsMessageKind.TEXT
        assert data.decode("utf-8") == "héllo ☃"

    def test_non_str_rejected(self) -> None:
        with pytest.raises(ValueError):
            encode_text_message(b"bytes")  # type: ignore[arg-type]


class TestEncodeBinary:
    def test_round_trip(self) -> None:
        blob = bytes(range(256))
        kind, data = decode_ws_message(encode_binary_message(blob))
        assert kind is WsMessageKind.BINARY
        assert data == blob

    def test_empty_bytes_round_trips(self) -> None:
        kind, data = decode_ws_message(encode_binary_message(b""))
        assert kind is WsMessageKind.BINARY
        assert data == b""

    def test_bytearray_accepted(self) -> None:
        kind, data = decode_ws_message(encode_binary_message(bytearray(b"\x01\x02")))
        assert kind is WsMessageKind.BINARY
        assert data == b"\x01\x02"

    def test_non_bytes_rejected(self) -> None:
        with pytest.raises(ValueError):
            encode_binary_message("text")  # type: ignore[arg-type]


class TestDecode:
    def test_empty_payload_rejected(self) -> None:
        with pytest.raises(TunnelError):
            decode_ws_message(b"")

    def test_unknown_marker_rejected(self) -> None:
        with pytest.raises(TunnelError):
            decode_ws_message(b"\xff payload")

    def test_text_marker_is_0x00_binary_is_0x01(self) -> None:
        """Wire-format stability: markers are part of the tunnel protocol."""
        assert encode_text_message("a")[0] == 0x00
        assert encode_binary_message(b"a")[0] == 0x01
