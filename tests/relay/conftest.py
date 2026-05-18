"""Test infrastructure for relay package tests."""

import asyncio
import json
import os
import time

import httpx
import pytest
from httpx import AsyncClient

from relay.app.main import create_relay_app
from relay.app.services.mount_registry import set_registry
from relay.app.services.sqlite_registry import SqliteMountRegistry


class MockTunnelConnection:
    """Full-interface mock TunnelConnection for proxy endpoint tests.

    Supports the complete proxy flow: stream open, send_open, read_stream
    (returns configured response metadata JSON), read_stream_iter (yields
    body chunks), send_data, and send_cancel. The run_receive_loop awaits a
    killswitch event so tests can simulate disconnect without blocking.
    """

    def __init__(self) -> None:
        self.closed: bool = False
        self.opened_streams: list = []
        self.sent_opens: list[tuple] = []  # list of (request_id, metadata)
        self.sent_data: list[tuple] = []   # list of (request_id, payload)
        self.cancelled_streams: list = []
        # Configurable first chunk (response metadata JSON) returned by read_stream
        self.first_chunk: bytes = json.dumps(
            {"status": 200, "headers": {"content-type": "text/plain"}}
        ).encode()
        # Configurable body chunks returned by read_stream_iter
        self.body_chunks: list[bytes] = [b"hello world"]
        # Event that tests can set to unblock run_receive_loop
        self._killswitch: asyncio.Event = asyncio.Event()

    def open_stream(self, request_id) -> None:
        self.opened_streams.append(request_id)

    async def send_open(self, request_id, metadata: dict) -> None:
        self.sent_opens.append((request_id, metadata))

    async def send_data(self, request_id, payload: bytes) -> None:
        self.sent_data.append((request_id, payload))

    async def read_stream(self, request_id, timeout_s: float) -> bytes:
        return self.first_chunk

    async def read_stream_iter(self, request_id):
        for chunk in self.body_chunks:
            yield chunk

    async def send_cancel(self, request_id) -> None:
        self.cancelled_streams.append(request_id)

    async def send_control(self, message: dict) -> None:
        pass

    async def receive_control(self) -> dict:
        return {"type": "pong"}

    def start_heartbeat(self, heartbeat_interval_s: float, missed_limit: int) -> None:
        pass

    async def run_receive_loop(self) -> None:
        await self._killswitch.wait()

    async def close(self) -> None:
        self.closed = True


async def _setup_in_memory_registry() -> SqliteMountRegistry:
    """Create an in-memory SqliteMountRegistry and install it as the global singleton.

    Used by test fixtures and test helpers when the ASGI transport does not
    trigger FastAPI lifespan events (e.g. httpx.ASGITransport, ASGIWebSocketTransport).
    """
    registry = await SqliteMountRegistry.create(":memory:")
    set_registry(registry)
    return registry


@pytest.fixture
async def relay_app(monkeypatch):
    """Create a fresh relay app with in-memory SQLite registry for each test.

    Creates the SqliteMountRegistry manually since httpx.ASGITransport does
    not trigger FastAPI lifespan events.
    """
    monkeypatch.setenv("RELAY_DB_PATH", ":memory:")
    app = create_relay_app()
    registry = await _setup_in_memory_registry()
    yield app
    await registry.close()


@pytest.fixture
async def relay_client(relay_app):
    """AsyncClient backed by the relay ASGI app."""
    transport = httpx.ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_connection() -> MockTunnelConnection:
    """Return a configured MockTunnelConnection."""
    return MockTunnelConnection()


@pytest.fixture
async def registered_relay_client(relay_app, mock_connection):
    """AsyncClient with a MockTunnelConnection pre-registered under 'testcode'.

    Returns a tuple of (client, registry) so tests can
    access the registry for state manipulation (e.g. mark_offline).
    """
    from relay.app.services.mount_registry import get_registry

    registry = get_registry()
    await registry.register(
        "testcode",
        mock_connection,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )
    transport = httpx.ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, registry


@pytest.fixture
async def account_store():
    """Install an in-memory accounts store as the global singleton."""
    from accounts import SqliteAccountStore
    from relay.app.services.account_store import set_account_store

    store = await SqliteAccountStore.create(":memory:")
    set_account_store(store)
    yield store
    set_account_store(None)
    await store.close()


@pytest.fixture
def relay_session():
    """Install a deterministic RelaySession as the global singleton."""
    from relay.app.services.session import RelaySession, set_relay_session

    s = RelaySession("test-relay-secret")
    set_relay_session(s)
    yield s
    set_relay_session(None)


@pytest.fixture
async def auth_client(relay_app, account_store, relay_session):
    """AsyncClient with accounts store + session signer wired in."""
    transport = httpx.ASGITransport(app=relay_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def make_admin():
    """Return a helper that marks a username as a relay admin.

    Rewrites the global (frozen) RelayConfig; relay_app recreates config
    per test, so the mutation does not leak across tests.
    """
    import dataclasses

    from relay.app.config import get_config, set_config

    def _make_admin(username: str) -> None:
        cfg = get_config()
        set_config(
            dataclasses.replace(cfg, admin_users=[username.strip().lower()])
        )

    return _make_admin
