"""Accounts library — users, nested groups, credentials, quotas.

Framework-agnostic and self-contained (no FastAPI / web / cookie code), so
it can be dropped into other projects. Relay/agent/server are thin glue.

Public API re-exports — importers may use either:
    from accounts import SqliteAccountStore, hash_password, Role
    from accounts.sqlite_store import SqliteAccountStore
"""

from accounts.enums import AccessMode, Role, SubjectType
from accounts.exceptions import (
    AccountError,
    DuplicateMembershipError,
    GroupCycleError,
    GroupNameTakenError,
    GroupNotFoundError,
    InvalidCredentialsError,
    MembershipNotFoundError,
    QuotaNotSetError,
    UserNotFoundError,
    UsernameTakenError,
    WeakPasswordError,
)
from accounts.models import Group, Membership, User
from accounts.passwords import hash_password, verify_password
from accounts.resolve import resolve_user_groups
from accounts.sqlite_store import SqliteAccountStore
from accounts.store import AccountStore

__all__ = [
    # Enums
    "AccessMode",
    "Role",
    "SubjectType",
    # Models
    "Group",
    "Membership",
    "User",
    # Passwords
    "hash_password",
    "verify_password",
    # Store
    "AccountStore",
    "SqliteAccountStore",
    "resolve_user_groups",
    # Exceptions
    "AccountError",
    "DuplicateMembershipError",
    "GroupCycleError",
    "GroupNameTakenError",
    "GroupNotFoundError",
    "InvalidCredentialsError",
    "MembershipNotFoundError",
    "QuotaNotSetError",
    "UserNotFoundError",
    "UsernameTakenError",
    "WeakPasswordError",
]
