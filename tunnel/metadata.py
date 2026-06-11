"""Typed OPEN / WS_OPEN frame metadata with validation and size caps.

Both tunnel ends previously exchanged untyped JSON dicts: oversized header
sets could blow the frame limit mid-send and malformed payloads crashed the
agent with KeyError. These dataclasses are the single wire contract —
``to_payload`` enforces the size cap before a frame is built, and
``from_payload`` validates structure before any field is touched.
"""

import json
from dataclasses import dataclass
from typing import Any

from tunnel.exceptions import MetadataError, MetadataTooLargeError

# Generous for real-world header sets (a few KB) while far below
# MAX_PAYLOAD_BYTES, so metadata can never produce FrameTooLargeError.
METADATA_MAX_BYTES: int = 16384


def _require_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str):
        raise MetadataError(f"metadata field '{key}' must be a string")
    return value


def _require_headers(obj: dict[str, Any]) -> dict[str, str]:
    value = obj.get("headers")
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        raise MetadataError("metadata field 'headers' must be a dict[str, str]")
    return value


def _parse_json(raw: bytes) -> dict[str, Any]:
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataError(f"metadata payload is not valid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise MetadataError("metadata payload must be a JSON object")
    return obj


@dataclass(frozen=True)
class RequestMetadata:
    """HTTP request metadata carried by an OPEN frame."""

    method: str
    path: str
    query: str
    headers: dict[str, str]
    content_length: int

    def to_payload(self) -> bytes:
        """Serialize to a JSON payload, enforcing METADATA_MAX_BYTES.

        Raises:
            MetadataTooLargeError: If the serialized form exceeds the cap.
        """
        payload = json.dumps(
            {
                "method": self.method,
                "path": self.path,
                "query": self.query,
                "headers": self.headers,
                "content_length": self.content_length,
            }
        ).encode("utf-8")
        if len(payload) > METADATA_MAX_BYTES:
            raise MetadataTooLargeError(
                f"request metadata is {len(payload)} bytes "
                f"(cap {METADATA_MAX_BYTES}); refusing to build frame"
            )
        return payload

    @classmethod
    def from_payload(cls, raw: bytes) -> "RequestMetadata":
        """Parse and validate an OPEN frame payload.

        Raises:
            MetadataError: If the payload is malformed or missing fields.
        """
        if len(raw) > METADATA_MAX_BYTES:
            raise MetadataTooLargeError(
                f"request metadata is {len(raw)} bytes (cap {METADATA_MAX_BYTES})"
            )
        obj = _parse_json(raw)
        content_length = obj.get("content_length", 0)
        if not isinstance(content_length, int) or isinstance(content_length, bool):
            raise MetadataError("metadata field 'content_length' must be an int")
        return cls(
            method=_require_str(obj, "method"),
            path=_require_str(obj, "path"),
            query=_require_str(obj, "query"),
            headers=_require_headers(obj),
            content_length=content_length,
        )


@dataclass(frozen=True)
class WsOpenMetadata:
    """WebSocket bridge metadata carried by a WS_OPEN frame."""

    path: str
    query: str
    headers: dict[str, str]

    def to_payload(self) -> bytes:
        """Serialize to a JSON payload, enforcing METADATA_MAX_BYTES.

        Raises:
            MetadataTooLargeError: If the serialized form exceeds the cap.
        """
        payload = json.dumps(
            {"path": self.path, "query": self.query, "headers": self.headers}
        ).encode("utf-8")
        if len(payload) > METADATA_MAX_BYTES:
            raise MetadataTooLargeError(
                f"ws metadata is {len(payload)} bytes "
                f"(cap {METADATA_MAX_BYTES}); refusing to build frame"
            )
        return payload

    @classmethod
    def from_payload(cls, raw: bytes) -> "WsOpenMetadata":
        """Parse and validate a WS_OPEN frame payload.

        Raises:
            MetadataError: If the payload is malformed or missing fields.
        """
        if len(raw) > METADATA_MAX_BYTES:
            raise MetadataTooLargeError(
                f"ws metadata is {len(raw)} bytes (cap {METADATA_MAX_BYTES})"
            )
        obj = _parse_json(raw)
        return cls(
            path=_require_str(obj, "path"),
            query=_require_str(obj, "query"),
            headers=_require_headers(obj),
        )
