"""Tests for WebSocketClientAdapter — wraps websockets ClientConnection."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tunnel.protocol import WebSocketProtocol


pytestmark = pytest.mark.anyio


def _make_mock_ws() -> MagicMock:
    """Return a mock that mimics websockets.asyncio.client.ClientConnection.

    Uses spec so isinstance checks against ClientConnection work correctly.
    """
    from websockets.asyncio.client import ClientConnection
    mock = MagicMock(spec=ClientConnection)
    mock.send = AsyncMock()
    mock.recv = AsyncMock()
    return mock


async def test_send_bytes_calls_ws_send_with_bytes() -> None:
    """send_bytes(data) calls ws.send(data) with bytes argument."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    adapter = WebSocketClientAdapter(mock_ws)
    await adapter.send_bytes(b"hello")
    mock_ws.send.assert_awaited_once_with(b"hello")


async def test_send_text_calls_ws_send_with_str() -> None:
    """send_text(data) calls ws.send(data) with str argument."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    adapter = WebSocketClientAdapter(mock_ws)
    await adapter.send_text("hello")
    mock_ws.send.assert_awaited_once_with("hello")


async def test_receive_bytes_returns_bytes_from_recv() -> None:
    """receive_bytes() calls ws.recv(decode=False) and returns bytes."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = b"binary data"
    adapter = WebSocketClientAdapter(mock_ws)
    result = await adapter.receive_bytes()
    assert result == b"binary data"
    mock_ws.recv.assert_awaited_once_with(decode=False)


async def test_receive_bytes_raises_type_error_if_str_received() -> None:
    """receive_bytes() raises TypeError if ws.recv returns a str."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = "text data"  # wrong type
    adapter = WebSocketClientAdapter(mock_ws)
    with pytest.raises(TypeError):
        await adapter.receive_bytes()


async def test_receive_text_returns_str_from_recv() -> None:
    """receive_text() calls ws.recv(decode=True) and returns str."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = "text data"
    adapter = WebSocketClientAdapter(mock_ws)
    result = await adapter.receive_text()
    assert result == "text data"
    mock_ws.recv.assert_awaited_once_with(decode=True)


async def test_receive_text_raises_type_error_if_bytes_received() -> None:
    """receive_text() raises TypeError if ws.recv returns bytes."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = b"binary data"  # wrong type
    adapter = WebSocketClientAdapter(mock_ws)
    with pytest.raises(TypeError):
        await adapter.receive_text()


async def test_receive_returns_bytes_dict_for_bytes() -> None:
    """receive() wraps bytes result in {'bytes': ...}."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = b"payload"
    adapter = WebSocketClientAdapter(mock_ws)
    result = await adapter.receive()
    assert result == {"bytes": b"payload"}
    mock_ws.recv.assert_awaited_once_with(decode=None)


async def test_receive_returns_text_dict_for_str() -> None:
    """receive() wraps str result in {'text': ...}."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    mock_ws.recv.return_value = "text payload"
    adapter = WebSocketClientAdapter(mock_ws)
    result = await adapter.receive()
    assert result == {"text": "text payload"}


async def test_adapter_satisfies_websocket_protocol() -> None:
    """isinstance(adapter, WebSocketProtocol) returns True."""
    from agent.ws_adapter import WebSocketClientAdapter
    mock_ws = _make_mock_ws()
    adapter = WebSocketClientAdapter(mock_ws)
    assert isinstance(adapter, WebSocketProtocol)


def test_constructor_raises_type_error_for_non_client_connection() -> None:
    """Constructor raises TypeError if passed something other than ClientConnection."""
    from agent.ws_adapter import WebSocketClientAdapter
    with pytest.raises(TypeError):
        WebSocketClientAdapter("not a connection")  # type: ignore[arg-type]
