"""Tests for tunnel.metadata — typed OPEN/WS_OPEN metadata validation."""

import json

import pytest

from tunnel.exceptions import MetadataError, MetadataTooLargeError
from tunnel.metadata import METADATA_MAX_BYTES, RequestMetadata, WsOpenMetadata


def _req(**overrides) -> RequestMetadata:
    base = dict(
        method="GET",
        path="/files",
        query="path=docs",
        headers={"accept": "application/json"},
        content_length=0,
    )
    base.update(overrides)
    return RequestMetadata(**base)


class TestRequestMetadataRoundTrip:
    def test_round_trip_preserves_fields(self) -> None:
        meta = _req(method="POST", content_length=42)
        parsed = RequestMetadata.from_payload(meta.to_payload())
        assert parsed == meta

    def test_payload_is_json_object(self) -> None:
        obj = json.loads(_req().to_payload())
        assert obj["method"] == "GET"
        assert obj["content_length"] == 0


class TestRequestMetadataValidation:
    def test_missing_method_raises(self) -> None:
        raw = json.dumps({"path": "/x", "query": "", "headers": {}}).encode()
        with pytest.raises(MetadataError):
            RequestMetadata.from_payload(raw)

    def test_non_dict_payload_raises(self) -> None:
        with pytest.raises(MetadataError):
            RequestMetadata.from_payload(b'["not", "an", "object"]')

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(MetadataError):
            RequestMetadata.from_payload(b"\xff\xfe not json")

    def test_non_string_header_values_raise(self) -> None:
        raw = json.dumps(
            {"method": "GET", "path": "/x", "query": "", "headers": {"a": 1},
             "content_length": 0}
        ).encode()
        with pytest.raises(MetadataError):
            RequestMetadata.from_payload(raw)

    def test_bool_content_length_raises(self) -> None:
        raw = json.dumps(
            {"method": "GET", "path": "/x", "query": "", "headers": {},
             "content_length": True}
        ).encode()
        with pytest.raises(MetadataError):
            RequestMetadata.from_payload(raw)

    def test_missing_content_length_defaults_to_zero(self) -> None:
        raw = json.dumps(
            {"method": "GET", "path": "/x", "query": "", "headers": {}}
        ).encode()
        assert RequestMetadata.from_payload(raw).content_length == 0


class TestRequestMetadataSizeCap:
    def test_oversized_serialization_raises(self) -> None:
        meta = _req(headers={"x-big": "v" * (METADATA_MAX_BYTES + 1)})
        with pytest.raises(MetadataTooLargeError):
            meta.to_payload()

    def test_oversized_inbound_payload_raises(self) -> None:
        raw = b"x" * (METADATA_MAX_BYTES + 1)
        with pytest.raises(MetadataTooLargeError):
            RequestMetadata.from_payload(raw)

    def test_cap_is_below_frame_limit(self) -> None:
        from tunnel.constants import MAX_PAYLOAD_BYTES

        assert METADATA_MAX_BYTES < MAX_PAYLOAD_BYTES


class TestWsOpenMetadata:
    def test_round_trip(self) -> None:
        meta = WsOpenMetadata(path="/ws", query="device=a", headers={"host": "h"})
        assert WsOpenMetadata.from_payload(meta.to_payload()) == meta

    def test_missing_path_raises(self) -> None:
        raw = json.dumps({"query": "", "headers": {}}).encode()
        with pytest.raises(MetadataError):
            WsOpenMetadata.from_payload(raw)

    def test_oversized_raises(self) -> None:
        meta = WsOpenMetadata(
            path="/ws", query="", headers={"x": "v" * (METADATA_MAX_BYTES + 1)}
        )
        with pytest.raises(MetadataTooLargeError):
            meta.to_payload()
