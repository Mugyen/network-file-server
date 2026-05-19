"""Enumerations for the accounts library.

All modes/variants are enums (never bare string literals) so callers get
type-checked, exhaustive choices.
"""

from enum import Enum


class Role(str, Enum):
    """Permission a subject is granted on a mount.

    READ    -- browse/list/download only.
    WRITE   -- full access (read + upload/rename/delete).
    RECEIVE -- upload, plus see/download only the subject's own uploads.
    """

    READ = "read"
    WRITE = "write"
    RECEIVE = "receive"


class AccessMode(str, Enum):
    """Whether a mount is open to anyone or restricted to an allowlist."""

    OPEN = "open"
    RESTRICTED = "restricted"


class SubjectType(str, Enum):
    """The kind of entity a membership/allowlist entry refers to."""

    USER = "user"
    GROUP = "group"
