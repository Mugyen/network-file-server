"""User CRUD: happy, edge, failure."""

import pytest

from accounts import UsernameTakenError, UserNotFoundError, hash_password


async def test_create_and_fetch_user(store):
    u = await store.create_user("alice", hash_password("pw"), "alice@example.com")
    assert u.id > 0
    assert u.username == "alice"
    assert u.email == "alice@example.com"
    assert u.is_active is True

    by_name = await store.get_user_by_username("alice")
    by_id = await store.get_user_by_id(u.id)
    assert by_name == u == by_id


async def test_create_user_without_email(store):
    u = await store.create_user("bob", hash_password("pw"), None)
    assert u.email is None


async def test_username_trimmed(store):
    u = await store.create_user("  carol  ", hash_password("pw"), None)
    assert u.username == "carol"
    assert (await store.get_user_by_username("carol")).id == u.id


async def test_duplicate_username_rejected(store):
    await store.create_user("dave", hash_password("pw"), None)
    with pytest.raises(UsernameTakenError):
        await store.create_user("dave", hash_password("pw2"), None)


async def test_get_missing_user_raises(store):
    with pytest.raises(UserNotFoundError):
        await store.get_user_by_username("ghost")
    with pytest.raises(UserNotFoundError):
        await store.get_user_by_id(9999)


async def test_set_user_active_toggle(store):
    u = await store.create_user("erin", hash_password("pw"), None)
    await store.set_user_active(u.id, False)
    assert (await store.get_user_by_id(u.id)).is_active is False
    await store.set_user_active(u.id, True)
    assert (await store.get_user_by_id(u.id)).is_active is True


async def test_set_active_missing_user_raises(store):
    with pytest.raises(UserNotFoundError):
        await store.set_user_active(4242, False)


async def test_list_users_ordered(store):
    a = await store.create_user("a", hash_password("pw"), None)
    b = await store.create_user("b", hash_password("pw"), None)
    ids = [u.id for u in await store.list_users()]
    assert ids == [a.id, b.id]


async def test_create_user_invalid_inputs(store):
    with pytest.raises(ValueError):
        await store.create_user("", hash_password("pw"), None)
    with pytest.raises(ValueError):
        await store.create_user("zoe", b"", None)
