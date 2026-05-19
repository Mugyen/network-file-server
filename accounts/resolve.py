"""Transitive group-membership resolution with cycle detection.

This is the single implementation of the membership graph walk; the SQLite
store delegates ``resolve_user_group_ids`` here so the algorithm lives in
exactly one place.
"""

from typing import TYPE_CHECKING

from accounts.enums import SubjectType
from accounts.exceptions import GroupCycleError

if TYPE_CHECKING:
    from accounts.store import AccountStore


async def _collect_parents(
    store: "AccountStore",
    member_type: SubjectType,
    member_id: int,
    acc: set[int],
    path: frozenset[int],
) -> None:
    """DFS up the membership graph, accumulating ancestor group ids.

    ``path`` is the set of group ids on the current DFS branch; revisiting
    one signals a cycle (defensive — writes are cycle-guarded, but a
    corrupted store must fail loudly rather than loop forever).
    """
    parent_ids = await store.list_parent_group_ids(member_type, member_id)
    for parent_id in parent_ids:
        if parent_id in path:
            raise GroupCycleError(parent_id, parent_id)
        if parent_id in acc:
            # Already fully explored via another branch (DAG reconvergence).
            continue
        acc.add(parent_id)
        await _collect_parents(
            store,
            SubjectType.GROUP,
            parent_id,
            acc,
            path | {parent_id},
        )


async def resolve_user_groups(store: "AccountStore", user_id: int) -> set[int]:
    """Return every group id the user transitively belongs to.

    Raises:
        UserNotFoundError: the user does not exist.
        GroupCycleError: the membership graph contains a cycle.
    """
    # Validate the subject exists (raises UserNotFoundError).
    await store.get_user_by_id(user_id)

    resolved: set[int] = set()
    await _collect_parents(store, SubjectType.USER, user_id, resolved, frozenset())
    return resolved
