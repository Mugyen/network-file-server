"""Tests for the relay health endpoint."""

import time

import pytest

from relay.app.services.mount_registry import get_registry
from tests.relay.conftest import MockTunnelConnection


@pytest.mark.asyncio
async def test_health_returns_200(relay_client) -> None:
    """GET /health returns 200 with status ok and zero mount count."""
    response = await relay_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mounts"] == 0


@pytest.mark.asyncio
async def test_health_reports_mount_count(relay_client) -> None:
    """After registering 2 mounts, GET /health returns mounts: 2."""
    registry = get_registry()
    conn1 = MockTunnelConnection()
    conn2 = MockTunnelConnection()
    registry.register("mount-a", conn1, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)
    registry.register("mount-b", conn2, agent_ip="127.0.0.1", created_at=time.monotonic(), expires_at=None)

    response = await relay_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["mounts"] == 2
