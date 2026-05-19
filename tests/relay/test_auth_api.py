"""Relay auth API: signup, login, logout, me, agent-token."""

import pytest

from relay.app.services.session import SESSION_COOKIE_NAME

pytestmark = pytest.mark.usefixtures("auth_client")


async def test_signup_then_login_flow(auth_client):
    r = await auth_client.post(
        "/auth/signup",
        json={"username": "alice", "password": "hunter2", "email": "a@x.com"},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "alice"

    r = await auth_client.post(
        "/auth/login", json={"username": "alice", "password": "hunter2"}
    )
    assert r.status_code == 200
    assert r.json() == {"username": "alice", "is_admin": False}
    assert SESSION_COOKIE_NAME in r.cookies


async def test_signup_duplicate_username_409(auth_client):
    await auth_client.post(
        "/auth/signup", json={"username": "bob", "password": "pw1234"}
    )
    r = await auth_client.post(
        "/auth/signup", json={"username": "bob", "password": "other1"}
    )
    assert r.status_code == 409


async def test_signup_weak_password_400(auth_client):
    r = await auth_client.post(
        "/auth/signup", json={"username": "carol", "password": ""}
    )
    assert r.status_code == 400


async def test_login_bad_password_401(auth_client):
    await auth_client.post(
        "/auth/signup", json={"username": "dave", "password": "rightpw"}
    )
    r = await auth_client.post(
        "/auth/login", json={"username": "dave", "password": "wrongpw"}
    )
    assert r.status_code == 401


async def test_login_unknown_user_401(auth_client):
    r = await auth_client.post(
        "/auth/login", json={"username": "ghost", "password": "whatever"}
    )
    assert r.status_code == 401


async def test_me_requires_auth(auth_client):
    r = await auth_client.get("/auth/me")
    assert r.status_code == 401


async def test_me_returns_identity_after_login(auth_client):
    await auth_client.post(
        "/auth/signup", json={"username": "erin", "password": "pw1234"}
    )
    await auth_client.post(
        "/auth/login", json={"username": "erin", "password": "pw1234"}
    )
    r = await auth_client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "erin"
    assert body["is_admin"] is False


async def test_logout_clears_cookie(auth_client):
    await auth_client.post(
        "/auth/signup", json={"username": "frank", "password": "pw1234"}
    )
    await auth_client.post(
        "/auth/login", json={"username": "frank", "password": "pw1234"}
    )
    assert (await auth_client.get("/auth/me")).status_code == 200
    await auth_client.post("/auth/logout")
    auth_client.cookies.clear()
    assert (await auth_client.get("/auth/me")).status_code == 401


async def test_agent_token_roundtrip(auth_client, relay_session):
    await auth_client.post(
        "/auth/signup", json={"username": "grace", "password": "pw1234"}
    )
    r = await auth_client.post(
        "/auth/agent-token", json={"username": "grace", "password": "pw1234"}
    )
    assert r.status_code == 200
    token = r.json()["token"]
    assert relay_session.verify_agent_owner_token(token) == r.json()["user_id"]


async def test_agent_token_bad_creds_401(auth_client):
    await auth_client.post(
        "/auth/signup", json={"username": "heidi", "password": "pw1234"}
    )
    r = await auth_client.post(
        "/auth/agent-token", json={"username": "heidi", "password": "nope"}
    )
    assert r.status_code == 401


async def test_disabled_user_cannot_login(auth_client, account_store):
    await auth_client.post(
        "/auth/signup", json={"username": "ivan", "password": "pw1234"}
    )
    user = await account_store.get_user_by_username("ivan")
    await account_store.set_user_active(user.id, False)
    r = await auth_client.post(
        "/auth/login", json={"username": "ivan", "password": "pw1234"}
    )
    assert r.status_code == 401
