"""Group CRUD: happy, edge, failure."""

import pytest

from accounts import (
    GroupNameTakenError,
    GroupNotFoundError,
    SubjectType,
    hash_password,
)


async def test_create_and_fetch_group(store):
    g = await store.create_group("engineering")
    assert g.id > 0
    assert g.name == "engineering"
    assert (await store.get_group_by_id(g.id)) == g
    assert (await store.get_group_by_name("engineering")) == g


async def test_duplicate_group_name_rejected(store):
    await store.create_group("ops")
    with pytest.raises(GroupNameTakenError):
        await store.create_group("ops")


async def test_get_missing_group_raises(store):
    with pytest.raises(GroupNotFoundError):
        await store.get_group_by_id(123)
    with pytest.raises(GroupNotFoundError):
        await store.get_group_by_name("nope")


async def test_list_groups_ordered(store):
    g1 = await store.create_group("g1")
    g2 = await store.create_group("g2")
    assert [g.id for g in await store.list_groups()] == [g1.id, g2.id]


async def test_delete_group_cascades_memberships(store):
    parent = await store.create_group("parent")
    child = await store.create_group("child")
    user = await store.create_user("u", hash_password("pw"), None)
    await store.add_member(parent.id, SubjectType.GROUP, child.id)
    await store.add_member(child.id, SubjectType.USER, user.id)

    await store.delete_group(child.id)

    with pytest.raises(GroupNotFoundError):
        await store.get_group_by_id(child.id)
    # Edge from parent -> child must be gone too.
    assert await store.list_group_members(parent.id) == []


async def test_delete_missing_group_raises(store):
    with pytest.raises(GroupNotFoundError):
        await store.delete_group(777)
