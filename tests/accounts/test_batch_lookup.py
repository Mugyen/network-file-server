"""Tests for AccountStore.get_users_by_ids (batch lookup, N+1 elimination)."""

import pytest

from accounts import SqliteAccountStore
from accounts.passwords import hash_password


@pytest.fixture
async def store():
    s = await SqliteAccountStore.create(":memory:")
    yield s
    await s.close()


async def _make_user(store: SqliteAccountStore, name: str):
    return await store.create_user(name, hash_password("secret-pw"), None)


class TestGetUsersByIds:
    async def test_returns_all_requested_users(self, store) -> None:
        alice = await _make_user(store, "alice")
        bob = await _make_user(store, "bob")
        result = await store.get_users_by_ids([alice.id, bob.id])
        assert set(result.keys()) == {alice.id, bob.id}
        assert result[alice.id].username == "alice"
        assert result[bob.id].username == "bob"

    async def test_empty_list_returns_empty_dict(self, store) -> None:
        assert await store.get_users_by_ids([]) == {}

    async def test_missing_ids_are_absent_not_error(self, store) -> None:
        alice = await _make_user(store, "alice")
        result = await store.get_users_by_ids([alice.id, 99999])
        assert set(result.keys()) == {alice.id}

    async def test_duplicate_ids_collapse(self, store) -> None:
        alice = await _make_user(store, "alice")
        result = await store.get_users_by_ids([alice.id, alice.id, alice.id])
        assert set(result.keys()) == {alice.id}

    async def test_non_int_ids_rejected(self, store) -> None:
        with pytest.raises(ValueError):
            await store.get_users_by_ids(["1"])  # type: ignore[list-item]

    async def test_non_list_rejected(self, store) -> None:
        with pytest.raises(ValueError):
            await store.get_users_by_ids("1,2")  # type: ignore[arg-type]
