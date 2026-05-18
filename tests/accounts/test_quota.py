"""Per-user quota: happy, edge, failure."""

import pytest

from accounts import QuotaNotSetError, UserNotFoundError, hash_password


async def test_set_and_get_quota(store):
    u = await store.create_user("alice", hash_password("pw"), None)
    await store.set_user_quota(u.id, 1024)
    assert await store.get_user_quota(u.id) == 1024
    await store.set_user_quota(u.id, 2048)
    assert await store.get_user_quota(u.id) == 2048


async def test_get_unset_quota_raises(store):
    u = await store.create_user("bob", hash_password("pw"), None)
    with pytest.raises(QuotaNotSetError):
        await store.get_user_quota(u.id)


async def test_set_quota_missing_user_raises(store):
    with pytest.raises(UserNotFoundError):
        await store.set_user_quota(123, 100)


async def test_negative_quota_rejected(store):
    u = await store.create_user("carol", hash_password("pw"), None)
    with pytest.raises(ValueError):
        await store.set_user_quota(u.id, -1)
