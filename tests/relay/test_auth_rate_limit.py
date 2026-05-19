"""Auth endpoints are per-IP rate limited (v1.3 phase 9)."""

import os
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient

from accounts import SqliteAccountStore
from relay.app.main import create_relay_app
from relay.app.services.account_store import set_account_store
from relay.app.services.mount_registry import set_registry
from relay.app.services.session import RelaySession, set_relay_session
from relay.app.services.sqlite_registry import SqliteMountRegistry

pytestmark = pytest.mark.anyio


@pytest.fixture
async def limited_client():
    # Override the autouse relaxed limits with a strict signup limit.
    with patch.dict(
        os.environ,
        {
            "RELAY_DB_PATH": ":memory:",
            "RELAY_AUTH_SIGNUP_RATE": "2/minute",
            "RELAY_AUTH_LOGIN_RATE": "2/minute",
        },
    ):
        app = create_relay_app()
    registry = await SqliteMountRegistry.create(":memory:")
    set_registry(registry)
    store = await SqliteAccountStore.create(":memory:")
    set_account_store(store)
    set_relay_session(RelaySession("secret"))
    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    set_account_store(None)
    set_relay_session(None)
    await store.close()
    await registry.close()


async def test_signup_rate_limited(limited_client):
    ip = {"x-forwarded-for": "203.0.113.7"}  # unique IP for an isolated bucket
    r1 = await limited_client.post(
        "/auth/signup", json={"username": "a1", "password": "pw1234"},
        headers=ip,
    )
    r2 = await limited_client.post(
        "/auth/signup", json={"username": "a2", "password": "pw1234"},
        headers=ip,
    )
    r3 = await limited_client.post(
        "/auth/signup", json={"username": "a3", "password": "pw1234"},
        headers=ip,
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


async def test_login_rate_limited(limited_client):
    ip = {"x-forwarded-for": "203.0.113.8"}
    await limited_client.post(
        "/auth/signup", json={"username": "loginuser", "password": "pw1234"},
        headers={"x-forwarded-for": "203.0.113.9"},
    )
    codes = []
    for _ in range(3):
        r = await limited_client.post(
            "/auth/login",
            json={"username": "loginuser", "password": "pw1234"},
            headers=ip,
        )
        codes.append(r.status_code)
    assert codes[-1] == 429
