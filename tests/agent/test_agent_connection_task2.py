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
        app_factory=None,
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
            app_factory=lambda ctx: MagicMock(),
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
        app_factory=None,
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
            app_factory=lambda ctx: MagicMock(),
        )

    assert call_count == 3


@pytest.mark.asyncio
async def test_connect_and_serve_passes_context_to_app_factory(tmp_path: Path) -> None:
    """connect_and_serve hands the app factory a MountAppContext carrying the
    password hash, assigned mount code, folder, and relay URL."""
    from agent.connection import connect_and_serve

    assigned_code = "TESTCODE"
    captured: dict = {}

    def fake_app_factory(ctx) -> MagicMock:
        captured["ctx"] = ctx
        return MagicMock()

    mock_ws = MagicMock()
    mock_conn = MagicMock()
    mock_conn.receive_control = AsyncMock(
        return_value={"type": "mount_registered", "code": assigned_code}
    )
    mock_conn.start_heartbeat = MagicMock()
    mock_conn.close = AsyncMock()
    mock_conn.send_control = AsyncMock()
    mock_conn.set_control_handler = MagicMock()
    mock_conn._ws = MagicMock()
    mock_conn.run_receive_loop_with_handlers = AsyncMock(
        side_effect=ConnectionError("ws closed")
    )

    fake_hash = b"fakehashbytes"

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
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
            app_factory=fake_app_factory,
        )

    ctx = captured["ctx"]
    assert ctx.password_hash == fake_hash
    assert ctx.mount_code == assigned_code
    assert ctx.folder == tmp_path
    assert ctx.relay_url == "https://relay.example.com"


def test_build_mount_app_configures_server(tmp_path: Path) -> None:
    """The CLI composition root's factory wires MountAppContext into the
    server app's per-app config on app.state (the agent itself never
    touches server state)."""
    from agent.connection import MountAppContext
    from server.app.bootstrap import build_mount_app

    ctx = MountAppContext(
        folder=tmp_path,
        password_hash=None,
        mount_code="FACTORYCODE",
        relay_url="https://relay.example.com",
        identity_secret="ctx-secret",
    )
    app = build_mount_app(ctx)
    assert app is not None

    config = app.state.config
    assert config.mount_code == "FACTORYCODE"
    assert config.shared_folder == tmp_path
    assert config.identity_secret == "ctx-secret"
    assert config.password_hash is None


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
    mock_conn.set_control_handler = MagicMock()
    mock_conn._ws = MagicMock()
    # Simulate a long-running receive loop that only returns after a brief
    # sleep. The TTL is 0 seconds so it should expire almost immediately.
    receive_call_count = 0

    async def slow_loop(on_open, on_ws_open) -> None:
        nonlocal receive_call_count
        receive_call_count += 1
        await asyncio.sleep(0.05)  # Let the TTL fire
        raise ConnectionError("ws closed")

    mock_conn.run_receive_loop_with_handlers = slow_loop

    with (
        patch("agent.connection.websockets_connect") as mock_connect,
        patch("agent.connection.WebSocketClientAdapter", return_value=MagicMock()),
        patch("agent.connection.TunnelConnection", return_value=mock_conn),
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
                app_factory=lambda ctx: MagicMock(),
            )
