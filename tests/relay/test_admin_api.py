"""Relay admin API: gating + user/group/membership management."""

import pytest

pytestmark = pytest.mark.usefixtures("auth_client")


async def _signup(client, username, password="pw1234"):
    r = await client.post(
        "/auth/signup", json={"username": username, "password": password}
    )
    assert r.status_code == 200
    return r.json()


async def _login(client, username, password="pw1234"):
    r = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200


async def _login_as_admin(client, make_admin, username="root"):
    await _signup(client, username)
    make_admin(username)
    await _login(client, username)


async def test_admin_routes_require_auth(auth_client):
    assert (await auth_client.get("/admin/users")).status_code == 401


async def test_non_admin_forbidden(auth_client):
    await _signup(auth_client, "regular")
    await _login(auth_client, "regular")
    assert (await auth_client.get("/admin/users")).status_code == 403


async def test_admin_lists_users(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    await _signup(auth_client, "alice")
    r = await auth_client.get("/admin/users")
    assert r.status_code == 200
    usernames = {u["username"] for u in r.json()}
    assert {"root", "alice"} <= usernames


async def test_admin_toggle_user_active(auth_client, account_store, make_admin):
    await _login_as_admin(auth_client, make_admin)
    info = await _signup(auth_client, "bob")
    r = await auth_client.post(
        f"/admin/users/{info['id']}/active", json={"is_active": False}
    )
    assert r.status_code == 200
    assert (await account_store.get_user_by_id(info["id"])).is_active is False


async def test_admin_toggle_missing_user_404(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    r = await auth_client.post("/admin/users/9999/active", json={"is_active": True})
    assert r.status_code == 404


async def test_group_crud_and_duplicate(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    r = await auth_client.post("/admin/groups", json={"name": "engineering"})
    assert r.status_code == 200
    gid = r.json()["id"]

    dup = await auth_client.post("/admin/groups", json={"name": "engineering"})
    assert dup.status_code == 409

    groups = (await auth_client.get("/admin/groups")).json()
    assert any(g["id"] == gid for g in groups)

    assert (await auth_client.delete(f"/admin/groups/{gid}")).status_code == 200
    assert (await auth_client.delete("/admin/groups/9999")).status_code == 404


async def test_add_user_and_nested_group_members(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    await _signup(auth_client, "alice")

    parent = (await auth_client.post("/admin/groups", json={"name": "org"})).json()
    child = (await auth_client.post("/admin/groups", json={"name": "team"})).json()

    r = await auth_client.post(
        f"/admin/groups/{child['id']}/members",
        json={"member_type": "user", "member_ref": "alice"},
    )
    assert r.status_code == 200

    r = await auth_client.post(
        f"/admin/groups/{parent['id']}/members",
        json={"member_type": "group", "member_ref": "team"},
    )
    assert r.status_code == 200

    members = (
        await auth_client.get(f"/admin/groups/{parent['id']}/members")
    ).json()
    assert members == [{"member_type": "group", "member_id": child["id"]}]


async def test_add_member_unknown_ref_404(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    g = (await auth_client.post("/admin/groups", json={"name": "g"})).json()
    r = await auth_client.post(
        f"/admin/groups/{g['id']}/members",
        json={"member_type": "user", "member_ref": "nobody"},
    )
    assert r.status_code == 404


async def test_add_member_cycle_409(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    a = (await auth_client.post("/admin/groups", json={"name": "a"})).json()
    b = (await auth_client.post("/admin/groups", json={"name": "b"})).json()
    await auth_client.post(
        f"/admin/groups/{a['id']}/members",
        json={"member_type": "group", "member_ref": "b"},
    )
    r = await auth_client.post(
        f"/admin/groups/{b['id']}/members",
        json={"member_type": "group", "member_ref": "a"},
    )
    assert r.status_code == 409


async def test_remove_member_and_missing(auth_client, make_admin):
    await _login_as_admin(auth_client, make_admin)
    info = await _signup(auth_client, "carol")
    g = (await auth_client.post("/admin/groups", json={"name": "grp"})).json()
    await auth_client.post(
        f"/admin/groups/{g['id']}/members",
        json={"member_type": "user", "member_ref": "carol"},
    )
    r = await auth_client.request(
        "DELETE",
        f"/admin/groups/{g['id']}/members",
        json={"member_type": "user", "member_id": info["id"]},
    )
    assert r.status_code == 200
    r = await auth_client.request(
        "DELETE",
        f"/admin/groups/{g['id']}/members",
        json={"member_type": "user", "member_id": info["id"]},
    )
    assert r.status_code == 404
