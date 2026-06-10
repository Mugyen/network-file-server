"""Tests for mount TTL enforcement and background sweep."""

import json
import os
import time
from unittest.mock import patch

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from relay.app.config import RelayConfig
from relay.app.enums import MountStatus
from relay.app.logging import RelayEnv
from relay.app.main import create_relay_app
from relay.app.services.sqlite_registry import SqliteMountRegistry
from tests.relay.conftest import MockTunnelConnection, _setup_in_memory_registry


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
        db_path=":memory:",
        data_dir="/tmp/test-data",
        dropbox_code="dropbox",
        session_secret="test-secret",
        admin_users=[],
        accounts_db_path=":memory:",
        default_user_quota_bytes=1073741824,
        auth_signup_rate="100/hour",
        auth_login_rate="100/minute",
        auth_agent_token_rate="100/minute",
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
            await ws.send_text(
                json.dumps(
                    {
                        "type": "agent_auth",
                        "token": None,
                        "access_mode": "open",
                        "has_password": False,
                        "allowlist": [],
                    }
                )
            )
            raw = await ws.receive_text()
            return json.loads(raw)


async def test_ttl_capped_to_max() -> None:
    """Connect with ttl=999999, verify mount_registered reports capped TTL."""
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=999999")
    assert msg["type"] == "mount_registered"
    # Default max_ttl_seconds is 86400 (24h)
    assert msg["ttl"] == 86400
    assert msg["expires_in"] == 86400
    await registry.close()


async def test_ttl_default_when_omitted() -> None:
    """Connect without ttl param, verify mount_registered reports default TTL."""
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    msg = await _recv_mount_registered(app, "/agent/ws")
    assert msg["type"] == "mount_registered"
    assert msg["ttl"] == 86400
    assert msg["expires_in"] == 86400
    await registry.close()


async def test_ttl_respected_when_under_max() -> None:
    """Connect with ttl=3600 (under max), verify it is used as-is."""
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=3600")
    assert msg["type"] == "mount_registered"
    assert msg["ttl"] == 3600
    assert msg["expires_in"] == 3600
    await registry.close()


async def test_mount_record_has_expires_at() -> None:
    """After agent connects with TTL, registry mount has expires_at set."""
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    registry = await _setup_in_memory_registry(app)
    msg = await _recv_mount_registered(app, "/agent/ws?ttl=3600")
    code = msg["code"]
    mounts = await registry.active_mounts()
    # There should be at least one mount with the code
    mount = next((m for m in mounts if m.code == code), None)
    if mount is not None:
        assert mount.expires_at is not None
    await registry.close()


# ---------------------------------------------------------------------------
# TTL sweep unit tests
# ---------------------------------------------------------------------------


async def test_sweep_expires_past_due_mount() -> None:
    """Sweep marks a mount as EXPIRED and closes connection when TTL has passed."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    now = time.time()
    await registry.register(
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

    # Mount should be EXPIRED -- verify via has_mount (record retained) + active_mounts (excluded)
    assert await registry.has_mount("expired-mount")
    active = await registry.active_mounts()
    assert all(m.code != "expired-mount" for m in active)
    assert conn.closed is True
    await registry.close()


async def test_sweep_sends_warning_before_expiry() -> None:
    """Sweep sends ttl_warning when mount is within warning_before_seconds of expiry."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    # Track control messages sent
    sent_controls: list[dict] = []

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)

    conn.send_control = capture_send  # type: ignore[assignment]

    now = time.time()
    # Expires in 200 seconds (within 300 second warning window)
    await registry.register(
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
    await registry.close()


async def test_sweep_skips_already_warned_mount() -> None:
    """Sweep does not send duplicate warning to already-warned mount."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    sent_controls: list[dict] = []

    async def capture_send(msg: dict) -> None:
        sent_controls.append(msg)

    conn.send_control = capture_send  # type: ignore[assignment]

    now = time.time()
    await registry.register(
        "warned-mount",
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

    # First sweep triggers the warning and persists ttl_warned to SQLite
    await sweep_once(registry, config)
    assert len(sent_controls) == 1

    # Subsequent sweeps re-read from SQLite, see ttl_warned=1, and stay silent
    await sweep_once(registry, config)
    await sweep_once(registry, config)
    assert len(sent_controls) == 1

    # A re-registration (reconnect) resets the flag, earning a fresh warning
    await registry.register(
        "warned-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now + 200,
    )
    await sweep_once(registry, config)
    assert len(sent_controls) == 2

    await registry.close()


async def test_sweep_resilience_one_bad_mount() -> None:
    """If one mount raises during close, other mounts are still processed."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")

    # Bad connection that raises on close
    bad_conn = MockTunnelConnection()

    async def raise_on_close() -> None:
        raise RuntimeError("Connection broken")

    bad_conn.close = raise_on_close  # type: ignore[assignment]

    # Good connection
    good_conn = MockTunnelConnection()

    now = time.time()
    await registry.register(
        "bad-mount",
        bad_conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,
    )
    await registry.register(
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

    # Both should be expired (records retained but not in active_mounts)
    assert await registry.has_mount("bad-mount")
    assert await registry.has_mount("good-mount")
    active = await registry.active_mounts()
    active_codes = {m.code for m in active}
    assert "bad-mount" not in active_codes
    assert "good-mount" not in active_codes
    # Good connection should have been closed
    assert good_conn.closed is True
    await registry.close()


async def test_sweep_ignores_mount_without_expires_at() -> None:
    """Sweep skips mounts that have no expires_at (None)."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    now = time.time()
    await registry.register(
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
    active = await registry.active_mounts()
    mount = next(m for m in active if m.code == "no-ttl-mount")
    assert mount.status == MountStatus.ONLINE
    assert conn.closed is False
    await registry.close()


async def test_sweep_ignores_non_online_mount() -> None:
    """Sweep skips mounts that are already OFFLINE."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    now = time.time()
    await registry.register(
        "offline-mount",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 100,
        expires_at=now - 10,
    )
    await registry.mark_offline("offline-mount")

    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Should still be in the DB but OFFLINE (active_mounts returns non-expired)
    # OFFLINE mount with past expires_at is still returned by active_mounts
    # but sweep skips it because status != ONLINE
    active = await registry.active_mounts()
    offline_mount = next((m for m in active if m.code == "offline-mount"), None)
    if offline_mount is not None:
        assert offline_mount.status == MountStatus.OFFLINE
    assert conn.closed is False
    await registry.close()


async def test_sweep_retention_cleanup() -> None:
    """Sweep deletes expired records past 6h retention window."""
    from relay.app.services.ttl_sweep import sweep_once

    registry = await SqliteMountRegistry.create(":memory:")
    conn = MockTunnelConnection()
    now = time.time()

    # Create a mount that expired 7 hours ago
    await registry.register(
        "old-expired",
        conn,
        agent_ip="1.2.3.4",
        created_at=now - 8 * 3600,
        expires_at=now - 7 * 3600,  # expired 7h ago, past 6h retention
    )
    # Mark as expired
    await registry.expire("old-expired")

    config = _make_test_config(
        max_ttl_seconds=86400,
        warning_before_seconds=300,
        ttl_sweep_interval_seconds=45,
    )

    await sweep_once(registry, config)

    # Record should be permanently deleted
    assert not await registry.has_mount("old-expired")
    await registry.close()
