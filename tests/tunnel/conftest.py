"""Test infrastructure for tunnel package tests."""

import asyncio
from typing import Union

import pytest


class MockWebSocket:
    """In-memory mock implementing the WebSocketProtocol interface.

    Inbound frames (what the code under test will receive) are fed via
    feed_binary() and feed_text() helpers.  Outbound frames (what the code
    under test sends) are recorded in sent_bytes_frames and sent_text_frames.
    """

    def __init__(self) -> None:
        self._inbound: asyncio.Queue[Union[bytes, str]] = asyncio.Queue()
        self.sent_bytes_frames: list[bytes] = []
        self.sent_text_frames: list[str] = []

    # ------------------------------------------------------------------ #
    # Feed helpers — called by tests to stage inbound frames              #
    # ------------------------------------------------------------------ #

    def feed_binary(self, data: bytes) -> None:
        """Stage a binary frame for the mock to return from receive_bytes/receive."""
        self._inbound.put_nowait(data)

    def feed_text(self, data: str) -> None:
        """Stage a text frame for the mock to return from receive_text/receive."""
        self._inbound.put_nowait(data)

    # ------------------------------------------------------------------ #
    # WebSocketProtocol implementation                                     #
    # ------------------------------------------------------------------ #

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes_frames.append(data)

    async def send_text(self, data: str) -> None:
        self.sent_text_frames.append(data)

    async def receive_bytes(self) -> bytes:
        item = await self._inbound.get()
        if not isinstance(item, bytes):
            raise TypeError(f"Expected bytes frame, got {type(item).__name__}")
        return item

    async def receive_text(self) -> str:
        item = await self._inbound.get()
        if not isinstance(item, str):
            raise TypeError(f"Expected text frame, got {type(item).__name__}")
        return item

    async def receive(self) -> dict:
        """Unified receive — returns {"bytes": ...} or {"text": ...}."""
        item = await self._inbound.get()
        if isinstance(item, bytes):
            return {"bytes": item}
        return {"text": item}


@pytest.fixture
def mock_ws() -> MockWebSocket:
    """Pytest fixture providing a fresh MockWebSocket for each test."""
    return MockWebSocket()
