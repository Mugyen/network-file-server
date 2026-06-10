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
    """Whether a mount is open to anyone or restricted to an allowlist.

    LEGACY marks a pre-v1.3 mount row that predates the access-policy model
    (no explicit owner/access policy was ever recorded). It is treated as
    OPEN at authorization time, but as a named, auditable state rather than
    an implicit absence.
    """

    OPEN = "open"
    RESTRICTED = "restricted"
    LEGACY = "legacy"


class SubjectType(str, Enum):
    """The kind of entity a membership/allowlist entry refers to."""

    USER = "user"
    GROUP = "group"
