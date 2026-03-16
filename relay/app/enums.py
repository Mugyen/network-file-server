from enum import Enum


class MountStatus(str, Enum):
    """Lifecycle status of a mounted relay connection."""

    ONLINE = "online"
    OFFLINE = "offline"
    EXPIRED = "expired"
