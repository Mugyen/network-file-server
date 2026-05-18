"""Test infrastructure for the accounts library."""

import pytest

from accounts import SqliteAccountStore


@pytest.fixture
async def store():
    """A fresh in-memory SqliteAccountStore per test."""
    s = await SqliteAccountStore.create(":memory:")
    yield s
    await s.close()
