"""Storage-agnostic account store interface.

``AccountStore`` defines the full persistence contract. ``SqliteAccountStore``
is the concrete implementation. Other backends (e.g. Postgres) can be added
without touching callers.

Contract notes:
- Every method has a strict, fully-typed signature with no default arguments.
- Lookups raise typed exceptions (never return None) when a record is absent.
"""

from abc import ABC, abstractmethod

from accounts.enums import SubjectType
from accounts.models import Group, Membership, User


class AccountStore(ABC):
    """Abstract persistence interface for users, groups, memberships, quotas."""

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_user(
        self, username: str, password_hash: bytes, email: str | None
    ) -> User:
        """Create a user. Raises UsernameTakenError if the username exists."""

    @abstractmethod
    async def get_user_by_username(self, username: str) -> User:
        """Return the user. Raises UserNotFoundError if absent."""

    @abstractmethod
    async def get_user_by_id(self, user_id: int) -> User:
        """Return the user. Raises UserNotFoundError if absent."""

    @abstractmethod
    async def set_user_active(self, user_id: int, is_active: bool) -> None:
        """Enable/disable a user. Raises UserNotFoundError if absent."""

    @abstractmethod
    async def list_users(self) -> list[User]:
        """Return all users ordered by id ascending."""

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_group(self, name: str) -> Group:
        """Create a group. Raises GroupNameTakenError if the name exists."""

    @abstractmethod
    async def get_group_by_id(self, group_id: int) -> Group:
        """Return the group. Raises GroupNotFoundError if absent."""

    @abstractmethod
    async def get_group_by_name(self, name: str) -> Group:
        """Return the group. Raises GroupNotFoundError if absent."""

    @abstractmethod
    async def list_groups(self) -> list[Group]:
        """Return all groups ordered by id ascending."""

    @abstractmethod
    async def delete_group(self, group_id: int) -> None:
        """Delete a group and all memberships referencing it.

        Raises GroupNotFoundError if absent.
        """

    # ------------------------------------------------------------------
    # Memberships
    # ------------------------------------------------------------------

    @abstractmethod
    async def add_member(
        self, group_id: int, member_type: SubjectType, member_id: int
    ) -> None:
        """Add (member_type, member_id) to group_id.

        Raises:
            GroupNotFoundError: group_id or a group member does not exist.
            UserNotFoundError: a user member does not exist.
            DuplicateMembershipError: the edge already exists.
            GroupCycleError: a group member would create a cycle.
        """

    @abstractmethod
    async def remove_member(
        self, group_id: int, member_type: SubjectType, member_id: int
    ) -> None:
        """Remove a membership edge.

        Raises MembershipNotFoundError if the edge does not exist.
        """

    @abstractmethod
    async def list_group_members(self, group_id: int) -> list[Membership]:
        """Return direct members of a group. Raises GroupNotFoundError if absent."""

    @abstractmethod
    async def list_parent_group_ids(
        self, member_type: SubjectType, member_id: int
    ) -> list[int]:
        """Return ids of groups that DIRECTLY contain the given subject."""

    @abstractmethod
    async def resolve_user_group_ids(self, user_id: int) -> set[int]:
        """Return all group ids the user belongs to, transitively.

        Raises UserNotFoundError if the user does not exist.
        """

    # ------------------------------------------------------------------
    # Per-user quota (used by relay-hosted storage)
    # ------------------------------------------------------------------

    @abstractmethod
    async def set_user_quota(self, user_id: int, quota_bytes: int) -> None:
        """Set/replace a user's storage quota. Raises UserNotFoundError if absent."""

    @abstractmethod
    async def get_user_quota(self, user_id: int) -> int:
        """Return the user's quota in bytes.

        Raises QuotaNotSetError if no override is configured (caller falls
        back to a system default).
        """

    @abstractmethod
    async def close(self) -> None:
        """Release any underlying resources (connections, file handles)."""
