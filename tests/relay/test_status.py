"""Tests for GET /m/{code}/status endpoint."""

import time

import pytest

from relay.app.services.mount_registry import get_registry
from tests.relay.conftest import MockTunnelConnection


async def _register_mount(
    code: str,
    connection: MockTunnelConnection | None,
    expires_at: float | None,
) -> None:
    """Register a mount in the global registry."""
    registry = get_registry()
    await registry.register(
        code=code,
        connection=connection,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_status_online(relay_client) -> None:
    """ONLINE mount returns {"status": "online"}."""
    conn = MockTunnelConnection()
    await _register_mount("online1", conn, expires_at=None)

    resp = await relay_client.get("/m/online1/status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "online"}


@pytest.mark.asyncio
async def test_status_offline(relay_client) -> None:
    """OFFLINE mount returns {"status": "offline"}."""
    conn = MockTunnelConnection()
    await _register_mount("off1", conn, expires_at=None)

    registry = get_registry()
    await registry.mark_offline("off1")

    resp = await relay_client.get("/m/off1/status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "offline"}


@pytest.mark.asyncio
async def test_status_expired(relay_client) -> None:
    """EXPIRED mount returns {"status": "expired"}."""
    conn = MockTunnelConnection()
    await _register_mount("exp1", conn, expires_at=None)

    registry = get_registry()
    await registry.expire("exp1")

    resp = await relay_client.get("/m/exp1/status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "expired"}


@pytest.mark.asyncio
async def test_status_not_found(relay_client) -> None:
    """Unknown code returns {"status": "not_found"}."""
    resp = await relay_client.get("/m/nosuchcode/status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "not_found"}


@pytest.mark.asyncio
async def test_status_local_mount_no_connection(relay_client) -> None:
    """Local mount (connection=None, e.g. drop box) returns {"status": "online"}.

    After Plan 15-03, the drop box is registered with connection=None.
    The status endpoint must NOT return 500 for this case.
    """
    await _register_mount("localbox", None, expires_at=None)

    resp = await relay_client.get("/m/localbox/status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "online"}


@pytest.mark.asyncio
async def test_status_not_rate_limited(relay_client) -> None:
    """Status endpoint is NOT rate-limited by the proxy rate limiter."""
    conn = MockTunnelConnection()
    await _register_mount("ratetest", conn, expires_at=None)

    for _ in range(20):
        resp = await relay_client.get("/m/ratetest/status")
        assert resp.status_code == 200, f"Got {resp.status_code} — status endpoint should not be rate-limited"
