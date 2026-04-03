from enum import Enum


class FileType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"


class ConflictResolution(str, Enum):
    OVERWRITE = "overwrite"
    RENAME = "rename"
    SKIP = "skip"


class WSMessageType(str, Enum):
    """WebSocket message types for real-time communication."""
    TOAST = "toast"
    SNIPPET_UPDATED = "snippet_updated"
    SNIPPET_CREATED = "snippet_created"
    SNIPPET_DELETED = "snippet_deleted"
    REQUEST_CREATED = "request_created"
    REQUEST_FULFILLED = "request_fulfilled"
    REQUEST_DISMISSED = "request_dismissed"
    DEVICE_COUNT = "device_count"
    DEVICE_LIST = "device_list"
    SNIPPET_UPDATE = "snippet_update"


class ToastType(str, Enum):
    """Types of toast notifications broadcast via WebSocket."""
    FILE_UPLOADED = "file_uploaded"
    FILE_EXPIRED = "file_expired"
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    REQUEST_CREATED = "request_created"
    REQUEST_FULFILLED = "request_fulfilled"


class RequestStatus(str, Enum):
    """Status of a file request."""
    PENDING = "pending"
    FULFILLED = "fulfilled"
    DISMISSED = "dismissed"


class ShareTTL(int, Enum):
    """Time-to-live options for share links, in seconds."""
    FIFTEEN_MINUTES = 900
    ONE_HOUR = 3600
    SIX_HOURS = 21600
    TWENTY_FOUR_HOURS = 86400


class DeviceType(str, Enum):
    """Classification of connected device types."""
    PHONE = "phone"
    TABLET = "tablet"
    DESKTOP = "desktop"
