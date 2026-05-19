from enum import Enum


class MountStatus(str, Enum):
    """Lifecycle status of a mounted relay connection."""

    ONLINE = "online"
    OFFLINE = "offline"
    EXPIRED = "expired"


class AccessRequestStatus(str, Enum):
    """Lifecycle of a user's request to access a restricted mount."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
