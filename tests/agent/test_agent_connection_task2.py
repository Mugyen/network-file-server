"""Tests for Task 2 — TTL expiry, no-retry on AgentExpiredError, password_hash passthrough."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.exceptions import AgentExpiredError


@pytest.mark.asyncio
async def test_run_agent_loop_exits_cleanly_on_ttl_expiry(tmp_path: Path) -> None:
    """run_agent_loop catches AgentExpiredError and exits (does NOT retry)."""
    from agent.connection import run_agent_loop

    call_count = 0

    async def fake_connect_and_serve(
        relay_url: str,
        folder: Path,
        name: str,
        preferred_code: str | None,
        password_hash: bytes | None,
        ttl_seconds: int | None,
        owner=None,
    ) -> str:
        nonlocal call_count
        call_count += 1
        raise AgentExpiredError("Mount expired after TTL")

    with (
        patch("agent.connection.connect_and_serve", side_effect=fake_connect_and_serve),
        patch("agent.connection.print_reconnect_status"),
    ):
        await run_agent_loop(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            password_hash=None,
            ttl_seconds=None,
            owner=None,
        )

    # Must exit after first call — no retry
    assert call_count == 1


@pytest.mark.asyncio
async def test_run_agent_loop_still_retries_on_connection_error(tmp_path: Path) -> None:
    """run_agent_loop still retries on normal exceptions (ConnectionError etc.)."""
    from agent.connection import run_agent_loop

    call_count = 0

    async def fake_connect_and_serve(
        relay_url: str,
        folder: Path,
        name: str,
        preferred_code: str | None,
        password_hash: bytes | None,
        ttl_seconds: int | None,
        owner=None,
    ) -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("connection dropped")
        raise KeyboardInterrupt

    with (
        patch("agent.connection.connect_and_serve", side_effect=fake_connect_and_serve),
        patch("agent.connection.compute_backoff", return_value=0.0),
        patch("agent.connection.asyncio_sleep", return_value=None),
        patch("agent.connection.print_reconnect_status"),
    ):
        await run_agent_loop(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            password_hash=None,
            ttl_seconds=None,
            owner=None,
        )

    assert call_count == 3


@pytest.mark.asyncio
async def test_connect_and_serve_sets_password_hash_in_config(tmp_path: Path) -> None:
    """connect_and_serve passes password_hash to ServerConfig."""
    import hashlib
    from agent.connection import connect_and_serve

    assigned_code = "TESTCODE"
    captured_config = {}

    def fake_set_server_config(config) -> None:
        captured_config["config"] = config

    mock_ws = MagicMock()
    mock_conn = MagicMock()
    mock_conn.receive_control = AsyncMock(
        return_value={"type": "mount_registered", "code": assigned_code}
    )
    mock_conn.start_heartbeat = MagicMock()
    mock_conn.close = AsyncMock()
    mock_conn.send_control = AsyncMock()
    mock_conn._ws = MagicMock()
    mock_conn._ws.receive = AsyncMock(side_effect=ConnectionError("ws closed"))

    fake_hash = b"fakehashbytes"

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
        patch("agent.connection.set_server_config", side_effect=fake_set_server_config),
        patch("agent.connection.set_token_service"),
        patch("agent.connection.AuthTokenService"),
        patch("agent.connection.create_app", return_value=MagicMock()),
        patch("agent.connection.print_mounted"),
        patch("agent.connection.print_connected_status"),
    ):
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

        await connect_and_serve(
            relay_url="https://relay.example.com",
            folder=tmp_path,
            name="testfolder",
            preferred_code=None,
            password_hash=fake_hash,
            ttl_seconds=None,
            owner=None,
        )

    assert captured_config["config"].password_hash == fake_hash
    assert captured_config["config"].mount_code == assigned_code


@pytest.mark.asyncio
async def test_connect_and_serve_ttl_raises_agent_expired_error(tmp_path: Path) -> None:
    """When ttl_seconds is set and expires, AgentExpiredError is raised."""
    from agent.connection import connect_and_serve

    assigned_code = "TESTCODE"

    mock_ws = MagicMock()
    mock_conn = MagicMock()
    mock_conn.receive_control = AsyncMock(
        return_value={"type": "mount_registered", "code": assigned_code}
    )
    mock_conn.start_heartbeat = MagicMock()
    mock_conn.close = AsyncMock()
    mock_conn.send_control = AsyncMock()
    mock_conn._ws = MagicMock()
    # Simulate a long-running receive that only returns after a brief sleep
    # The TTL is 0 seconds so it should expire almost immediately
    receive_call_count = 0

    async def slow_receive() -> dict:
        nonlocal receive_call_count
        receive_call_count += 1
        await asyncio.sleep(0.05)  # Let the TTL fire
        raise ConnectionError("ws closed")

    mock_conn._ws.receive = slow_receive

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
        patch("agent.connection.set_server_config"),
        patch("agent.connection.set_token_service"),
        patch("agent.connection.AuthTokenService"),
        patch("agent.connection.create_app", return_value=MagicMock()),
        patch("agent.connection.print_mounted"),
        patch("agent.connection.print_connected_status"),
        patch("agent.connection._print_ttl_countdown", new_callable=AsyncMock),
    ):
        mock_connect.return_value.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_connect.return_value.__aexit__ = AsyncMock(return_value=None)

        with pytest.raises(AgentExpiredError):
            await connect_and_serve(
                relay_url="https://relay.example.com",
                folder=tmp_path,
                name="testfolder",
                preferred_code=None,
                password_hash=None,
                ttl_seconds=0,  # expires immediately
                owner=None,
            )
