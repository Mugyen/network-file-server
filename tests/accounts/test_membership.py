"""Membership edges, nested groups, cycle detection, transitive resolution."""

import pytest

from accounts import (
    DuplicateMembershipError,
    GroupCycleError,
    GroupNotFoundError,
    MembershipNotFoundError,
    SubjectType,
    UserNotFoundError,
    hash_password,
)


async def _user(store, name):
    return await store.create_user(name, hash_password("pw"), None)


async def test_add_and_list_members(store):
    g = await store.create_group("team")
    u = await _user(store, "alice")
    await store.add_member(g.id, SubjectType.USER, u.id)
    members = await store.list_group_members(g.id)
    assert len(members) == 1
    assert members[0].member_type is SubjectType.USER
    assert members[0].member_id == u.id


async def test_duplicate_membership_rejected(store):
    g = await store.create_group("team")
    u = await _user(store, "alice")
    await store.add_member(g.id, SubjectType.USER, u.id)
    with pytest.raises(DuplicateMembershipError):
        await store.add_member(g.id, SubjectType.USER, u.id)


async def test_add_member_validates_endpoints(store):
    g = await store.create_group("team")
    with pytest.raises(UserNotFoundError):
        await store.add_member(g.id, SubjectType.USER, 999)
    with pytest.raises(GroupNotFoundError):
        await store.add_member(g.id, SubjectType.GROUP, 999)
    u = await _user(store, "x")
    with pytest.raises(GroupNotFoundError):
        await store.add_member(999, SubjectType.USER, u.id)


async def test_remove_member(store):
    g = await store.create_group("team")
    u = await _user(store, "alice")
    await store.add_member(g.id, SubjectType.USER, u.id)
    await store.remove_member(g.id, SubjectType.USER, u.id)
    assert await store.list_group_members(g.id) == []


async def test_remove_missing_membership_raises(store):
    g = await store.create_group("team")
    with pytest.raises(MembershipNotFoundError):
        await store.remove_member(g.id, SubjectType.USER, 1)


async def test_self_membership_is_cycle(store):
    g = await store.create_group("g")
    with pytest.raises(GroupCycleError):
        await store.add_member(g.id, SubjectType.GROUP, g.id)


async def test_two_node_cycle_rejected(store):
    a = await store.create_group("a")
    b = await store.create_group("b")
    await store.add_member(a.id, SubjectType.GROUP, b.id)  # a contains b
    with pytest.raises(GroupCycleError):
        await store.add_member(b.id, SubjectType.GROUP, a.id)  # would close loop


async def test_three_node_cycle_rejected(store):
    a = await store.create_group("a")
    b = await store.create_group("b")
    c = await store.create_group("c")
    await store.add_member(a.id, SubjectType.GROUP, b.id)
    await store.add_member(b.id, SubjectType.GROUP, c.id)
    with pytest.raises(GroupCycleError):
        await store.add_member(c.id, SubjectType.GROUP, a.id)


async def test_resolve_three_level_nesting(store):
    # org contains dept contains team contains alice
    org = await store.create_group("org")
    dept = await store.create_group("dept")
    team = await store.create_group("team")
    alice = await _user(store, "alice")
    await store.add_member(org.id, SubjectType.GROUP, dept.id)
    await store.add_member(dept.id, SubjectType.GROUP, team.id)
    await store.add_member(team.id, SubjectType.USER, alice.id)

    resolved = await store.resolve_user_group_ids(alice.id)
    assert resolved == {org.id, dept.id, team.id}


async def test_resolve_diamond_reconvergence(store):
    # top contains left and right; both contain team; team contains bob.
    top = await store.create_group("top")
    left = await store.create_group("left")
    right = await store.create_group("right")
    team = await store.create_group("team")
    bob = await _user(store, "bob")
    await store.add_member(top.id, SubjectType.GROUP, left.id)
    await store.add_member(top.id, SubjectType.GROUP, right.id)
    await store.add_member(left.id, SubjectType.GROUP, team.id)
    await store.add_member(right.id, SubjectType.GROUP, team.id)
    await store.add_member(team.id, SubjectType.USER, bob.id)

    resolved = await store.resolve_user_group_ids(bob.id)
    assert resolved == {top.id, left.id, right.id, team.id}


async def test_resolve_user_with_no_groups(store):
    u = await _user(store, "loner")
    assert await store.resolve_user_group_ids(u.id) == set()


async def test_resolve_missing_user_raises(store):
    with pytest.raises(UserNotFoundError):
        await store.resolve_user_group_ids(31337)
