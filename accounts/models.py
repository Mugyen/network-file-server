"""Immutable domain models for the accounts library."""

from dataclasses import dataclass

from accounts.enums import SubjectType


@dataclass(frozen=True)
class User:
    """A registered account.

    ``email`` is optional and is NOT used for authentication — the unique
    ``username`` is the login identifier.
    """

    id: int
    username: str
    email: str | None
    password_hash: bytes
    created_at: float
    is_active: bool


@dataclass(frozen=True)
class Group:
    """A named collection that can contain users and/or other groups."""

    id: int
    name: str
    created_at: float


@dataclass(frozen=True)
class Membership:
    """A single membership edge: ``group_id`` contains (member_type, member_id)."""

    group_id: int
    member_type: SubjectType
    member_id: int
