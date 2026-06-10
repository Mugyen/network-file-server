"""Per-user relay storage: quota enforcement + isolation."""

import io

import httpx
import pytest
from httpx import AsyncClient

from accounts import SqliteAccountStore
from relay.app.main import create_relay_app
from relay.app.services.session import RelaySession
from relay.app.services.sqlite_registry import SqliteMountRegistry

pytestmark = pytest.mark.anyio


@pytest.fixture
async def storage_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_DB_PATH", ":memory:")
    monkeypatch.setenv("RELAY_DATA_DIR", str(tmp_path))
    app = create_relay_app()
    registry = await SqliteMountRegistry.create(":memory:")
    app.state.relay.registry = registry
    store = await SqliteAccountStore.create(":memory:")
    app.state.relay.account_store = store
    app.state.relay.session = RelaySession("secret")
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, store
    await store.close()
    await registry.close()


async def _signup_login(client, username: str) -> None:
    await client.post(
        "/auth/signup", json={"username": username, "password": "pw1234"}
    )
    r = await client.post(
        "/auth/login", json={"username": username, "password": "pw1234"}
    )
    assert r.status_code == 200


async def test_requires_login(storage_client):
    client, _store = storage_client
    assert (await client.get("/me/files")).status_code == 401
    assert (await client.get("/me/quota")).status_code == 401


async def test_upload_list_download_roundtrip(storage_client):
    client, _store = storage_client
    await _signup_login(client, "alice")
    up = await client.post(
        "/me/files/upload",
        files={"files": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert up.status_code == 200
    listing = await client.get("/me/files")
    names = {e["name"] for e in listing.json()["entries"]}
    assert "a.txt" in names
    dl = await client.get("/me/files/download", params={"path": "a.txt"})
    assert dl.status_code == 200
    assert dl.content == b"hello"


async def test_quota_exceeded_returns_413(storage_client):
    client, store = storage_client
    await _signup_login(client, "bob")
    user = await store.get_user_by_username("bob")
    await store.set_user_quota(user.id, 4)  # 4 bytes
    r = await client.post(
        "/me/files/upload",
        files={"files": ("big.txt", io.BytesIO(b"way too big"), "text/plain")},
    )
    assert r.status_code == 413


async def test_quota_endpoint_reports_usage(storage_client):
    client, store = storage_client
    await _signup_login(client, "carol")
    user = await store.get_user_by_username("carol")
    await store.set_user_quota(user.id, 1000)
    await client.post(
        "/me/files/upload",
        files={"files": ("c.txt", io.BytesIO(b"abcde"), "text/plain")},
    )
    q = (await client.get("/me/quota")).json()
    assert q["quota"] == 1000
    assert q["usage"] >= 5


async def test_user_isolation(storage_client):
    client, _store = storage_client
    await _signup_login(client, "alice")
    await client.post(
        "/me/files/upload",
        files={"files": ("secret.txt", io.BytesIO(b"x"), "text/plain")},
    )
    await client.post("/auth/logout")
    client.cookies.clear()
    await _signup_login(client, "mallory")
    listing = await client.get("/me/files")
    names = {e["name"] for e in listing.json()["entries"]}
    assert "secret.txt" not in names
    dl = await client.get("/me/files/download", params={"path": "secret.txt"})
    assert dl.status_code == 404


async def test_usage_recomputed_after_delete(storage_client):
    client, store = storage_client
    await _signup_login(client, "dave")
    user = await store.get_user_by_username("dave")
    await store.set_user_quota(user.id, 1000)
    await client.post(
        "/me/files/upload",
        files={"files": ("d.txt", io.BytesIO(b"123456789"), "text/plain")},
    )
    before = (await client.get("/me/quota")).json()["usage"]
    assert before >= 9
    await client.request(
        "DELETE", "/me/files", json={"paths": ["d.txt"]}
    )
    after = (await client.get("/me/quota")).json()["usage"]
    assert after == 0
