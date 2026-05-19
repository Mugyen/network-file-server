"""Typed exceptions for the accounts library.

Every failure mode raises a specific ``AccountError`` subclass. Library
functions never return ``None``/sentinels to signal "not found" or
"invalid" — they raise.
"""


class AccountError(Exception):
    """Base class for all accounts-library errors."""


class UsernameTakenError(AccountError):
    """Raised when creating a user whose username already exists."""

    def __init__(self, username: str) -> None:
        super().__init__(f"Username already taken: {username!r}")
        self.username = username


class UserNotFoundError(AccountError):
    """Raised when a user lookup finds no matching record."""

    def __init__(self, identifier: object) -> None:
        super().__init__(f"User not found: {identifier!r}")
        self.identifier = identifier


class GroupNotFoundError(AccountError):
    """Raised when a group lookup finds no matching record."""

    def __init__(self, identifier: object) -> None:
        super().__init__(f"Group not found: {identifier!r}")
        self.identifier = identifier


class GroupNameTakenError(AccountError):
    """Raised when creating a group whose name already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Group name already taken: {name!r}")
        self.name = name


class GroupCycleError(AccountError):
    """Raised when a membership change would create a group cycle."""

    def __init__(self, group_id: int, member_group_id: int) -> None:
        super().__init__(
            f"Adding group {member_group_id} to group {group_id} would create a cycle"
        )
        self.group_id = group_id
        self.member_group_id = member_group_id


class DuplicateMembershipError(AccountError):
    """Raised when adding a membership that already exists."""

    def __init__(self, group_id: int, member_type: object, member_id: int) -> None:
        super().__init__(
            f"Membership already exists: group={group_id} "
            f"member_type={member_type} member_id={member_id}"
        )
        self.group_id = group_id
        self.member_type = member_type
        self.member_id = member_id


class MembershipNotFoundError(AccountError):
    """Raised when removing a membership that does not exist."""

    def __init__(self, group_id: int, member_type: object, member_id: int) -> None:
        super().__init__(
            f"Membership not found: group={group_id} "
            f"member_type={member_type} member_id={member_id}"
        )
        self.group_id = group_id
        self.member_type = member_type
        self.member_id = member_id


class InvalidCredentialsError(AccountError):
    """Raised when authentication fails (bad username or password)."""

    def __init__(self) -> None:
        # Deliberately generic: do not leak whether the username exists.
        super().__init__("Invalid username or password")


class WeakPasswordError(AccountError):
    """Raised when a password violates basic constraints (empty / too long)."""


class QuotaNotSetError(AccountError):
    """Raised when reading a per-user quota that has not been configured.

    Callers are expected to fall back to a system default.
    """

    def __init__(self, user_id: int) -> None:
        super().__init__(f"No quota set for user {user_id}")
        self.user_id = user_id
