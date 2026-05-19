"""Access-request workflow + relay SPA page routes."""

import time

import pytest

from accounts import AccessMode, SubjectType

pytestmark = pytest.mark.usefixtures("auth_client")


async def _signup_login(client, username, password="pw1234"):
    await client.post(
        "/auth/signup", json={"username": username, "password": password}
    )
    r = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200
    me = await client.get("/auth/me")
    return me.json()["user_id"]


async def _register_owned_mount(registry, code, owner_id):
    await registry.register(
        code, None, agent_ip="127.0.0.1", created_at=time.time(),
        expires_at=None,
    )
    await registry.set_owner_policy(
        code, owner_id, AccessMode.RESTRICTED, False, []
    )


@pytest.fixture
def registry():
    from relay.app.services.mount_registry import get_registry

    return get_registry()


async def test_create_request_requires_login(auth_client):
    r = await auth_client.post("/requests", json={"code": "m1"})
    assert r.status_code == 401


async def test_create_request_dedupes(auth_client):
    await _signup_login(auth_client, "alice")
    r1 = await auth_client.post("/requests", json={"code": "m1"})
    r2 = await auth_client.post("/requests", json={"code": "m1"})
    assert r1.status_code == 200
    assert r1.json()["status"] == "pending"
    assert r1.json()["id"] == r2.json()["id"]


async def test_owner_sees_and_approves_request(auth_client, registry):
    requester_id = await _signup_login(auth_client, "bob")
    await auth_client.post("/requests", json={"code": "ownedm"})
    await auth_client.post("/auth/logout")
    auth_client.cookies.clear()

    owner_id = await _signup_login(auth_client, "owner")
    await _register_owned_mount(registry, "ownedm", owner_id)

    listing = await auth_client.get("/requests")
    assert listing.status_code == 200
    items = listing.json()
    assert any(i["code"] == "ownedm" and i["username"] == "bob" for i in items)
    req_id = next(i["id"] for i in items if i["code"] == "ownedm")

    r = await auth_client.post(
        f"/requests/{req_id}/resolve",
        json={"action": "approve", "role": "write"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    policy = await registry.get_policy("ownedm")
    assert any(
        e.subject_type is SubjectType.USER and e.subject_id == requester_id
        for e in policy.entries
    )


async def test_non_owner_non_admin_cannot_resolve(auth_client, registry):
    await _signup_login(auth_client, "carol")
    await auth_client.post("/requests", json={"code": "m2"})
    await auth_client.post("/auth/logout")
    auth_client.cookies.clear()

    owner_id = await _signup_login(auth_client, "realowner")
    await _register_owned_mount(registry, "m2", owner_id)
    listing = await auth_client.get("/requests")
    req_id = next(i["id"] for i in listing.json() if i["code"] == "m2")
    await auth_client.post("/auth/logout")
    auth_client.cookies.clear()

    await _signup_login(auth_client, "stranger")
    r = await auth_client.post(
        f"/requests/{req_id}/resolve", json={"action": "deny"}
    )
    assert r.status_code == 403


async def test_admin_can_deny(auth_client, registry, make_admin):
    await _signup_login(auth_client, "dave")
    await auth_client.post("/requests", json={"code": "m3"})
    await auth_client.post("/auth/logout")
    auth_client.cookies.clear()

    await _signup_login(auth_client, "root")
    make_admin("root")
    await _register_owned_mount(registry, "m3", 999)  # owner is someone else
    listing = await auth_client.get("/requests")  # admin sees all
    req_id = next(i["id"] for i in listing.json() if i["code"] == "m3")
    r = await auth_client.post(
        f"/requests/{req_id}/resolve", json={"action": "deny"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "denied"


async def test_resolve_unknown_request_404(auth_client, make_admin):
    await _signup_login(auth_client, "root")
    make_admin("root")
    r = await auth_client.post(
        "/requests/99999/resolve", json={"action": "deny"}
    )
    assert r.status_code == 404


@pytest.mark.parametrize("path", ["/login", "/signup", "/admin", "/403"])
async def test_spa_page_routes_serve_html(auth_client, path):
    r = await auth_client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
