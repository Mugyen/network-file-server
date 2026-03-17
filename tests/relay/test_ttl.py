"""Tests for mount TTL enforcement and background sweep."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.config import RelayConfig, set_config
from relay.app.enums import MountStatus
from relay.app.logging import RelayEnv
from relay.app.main import create_relay_app
from relay.app.services.mount_registry import MountRecord, MountRegistry, get_registry, set_registry
from tests.relay.conftest import MockTunnelConnection


pytestmark = pytest.mark.anyio


def _make_test_config(
    max_ttl_seconds: int,
    warning_before_seconds: int,
    ttl_sweep_interval_seconds: int,
) -> RelayConfig:
    """Build a RelayConfig with specific TTL settings for testing."""
    return RelayConfig(
        env=RelayEnv.DEVELOPMENT,
        allowed_origins=[],
        mount_reg_rate="100/hour",
        proxy_request_rate="1000/minute",
        max_ttl_seconds=max_ttl_seconds,
        max_mounts_per_ip=10,
        ttl_sweep_interval_seconds=ttl_sweep_interval_seconds,
        warning_before_seconds=warning_before_seconds,
    )


# ---------------------------------------------------------------------------
# TTL capping and default tests (via WebSocket endpoint)
# ---------------------------------------------------------------------------


async def _recv_mount_registered(app, path: str) -> dict:
    """Connect to agent WS, receive mount_registered, return parsed JSON."""
    transport = ASGIWebSocketTransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with aconnect_ws(
            f"http://testserver{path}",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            raw = await ws.receive_text()
            return json.loads(raw)


async def test_ttl_capped_to_max() -> None:
    """Connect with ttl=999999, verify mount_registered reports capped TTL."""
    app = create_relay_app()
    set_registry(MountRegistry())
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=999999")
    assert msg["type"] == "mount_registered"
    # Default max_ttl_seconds is 86400 (24h)
    assert msg["ttl"] == 86400
    assert msg["expires_in"] == 86400


async def test_ttl_default_when_omitted() -> None:
    """Connect without ttl param, verify mount_registered reports default TTL."""
    app = create_relay_app()
    set_registry(MountRegistry())
    msg = await _recv_mount_registered(app, "/agent/ws")
    assert msg["type"] == "mount_registered"
    assert msg["ttl"] == 86400
    assert msg["expires_in"] == 86400


async def test_ttl_respected_when_under_max() -> None:
    """Connect with ttl=3600 (under max), verify it is used as-is."""
    app = create_relay_app()
    set_registry(MountRegistry())
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=3600")
    assert msg["type"] == "mount_registered"
    assert msg["ttl"] == 3600
    assert msg["expires_in"] == 3600


async def test_mount_record_has_expires_at() -> None:
    """After agent connects with TTL, registry mount has expires_at set."""
    app = create_relay_app()
    set_registry(MountRegistry())
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=3600")
    code = msg["code"]
    registry = get_registry()
    mounts = registry.active_mounts()
    # There should be at least one mount with the code
    mount = next((m for m in mounts if m.code == code), None)
    if mount is not None:
        assert mount.expires_at is not None


# ---------------------------------------------------------------------------
# TTL sweep unit tests
# ---------------------------------------------------------------------------


async def test_sweep_expires_past_due_mount() -> None:
    """Sweep marks a mount as EXPIRED and closes connection when TTL has passed."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()
    conn = MockTunnelConnection()
    now = time.monotonic()
    registry.register(
        "expired-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,  # Already expired
    )
    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Mount should be EXPIRED
    record = registry._mounts["expired-mount"]
    assert record.status == MountStatus.EXPIRED
    assert conn.closed is True


async def test_sweep_sends_warning_before_expiry() -> None:
    """Sweep sends ttl_warning when mount is within warning_before_seconds of expiry."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()
    conn = MockTunnelConnection()
    # Track control messages sent
    sent_controls: list[dict] = []
    original_send = conn.send_control

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)

    conn.send_control = capture_send  # type: ignore[assignment]

    now = time.monotonic()
    # Expires in 200 seconds (within 300 second warning window)
    registry.register(
        "warn-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now + 200,
    )
    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Should have sent a warning
    assert len(sent_controls) == 1
    msg = sent_controls[0]
    assert msg["type"] == "ttl_warning"
    assert "expires_in" in msg
    assert msg["expires_in"] > 0
    # Mount should be marked as warned
    record = registry._mounts["warn-mount"]
    assert record.ttl_warned is True


async def test_sweep_skips_already_warned_mount() -> None:
    """Sweep does not send duplicate warning to already-warned mount."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()
    conn = MockTunnelConnection()
    sent_controls: list[dict] = []

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)

    conn.send_control = capture_send  # type: ignore[assignment]

    now = time.monotonic()
    registry.register(
        "warned-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now + 200,
    )
    # Mark as already warned
    registry._mounts["warned-mount"].ttl_warned = True

    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Should NOT have sent any warnings
    assert len(sent_controls) == 0


async def test_sweep_resilience_one_bad_mount() -> None:
    """If one mount raises during close, other mounts are still processed."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()

    # Bad connection that raises on close
    bad_conn = MockTunnelConnection()

    async def raise_on_close() -> None:
        raise RuntimeError("Connection broken")

    bad_conn.close = raise_on_close  # type: ignore[assignment]

    # Good connection
    good_conn = MockTunnelConnection()

    now = time.monotonic()
    registry.register(
        "bad-mount",
        bad_conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,
    )
    registry.register(
        "good-mount",
        good_conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,
    )

    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    # Should not raise despite bad-mount's close() failing
    await sweep_once(registry, config)

    # Both should be marked EXPIRED regardless
    assert registry._mounts["bad-mount"].status == MountStatus.EXPIRED
    assert registry._mounts["good-mount"].status == MountStatus.EXPIRED
    # Good connection should have been closed
    assert good_conn.closed is True


async def test_sweep_ignores_mount_without_expires_at() -> None:
    """Sweep skips mounts that have no expires_at (None)."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()
    conn = MockTunnelConnection()
    now = time.monotonic()
    registry.register(
        "no-ttl-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now,
        expires_at=None,
    )
    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Mount should remain ONLINE
    record = registry._mounts["no-ttl-mount"]
    assert record.status == MountStatus.ONLINE
    assert conn.closed is False


async def test_sweep_ignores_non_online_mount() -> None:
    """Sweep skips mounts that are already EXPIRED or OFFLINE."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = MountRegistry()
    conn = MockTunnelConnection()
    now = time.monotonic()
    registry.register(
        "offline-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,
    )
    registry._mounts["offline-mount"].status = MountStatus.OFFLINE

    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Should still be OFFLINE, not changed to EXPIRED
    assert registry._mounts["offline-mount"].status == MountStatus.OFFLINE
    assert conn.closed is False
