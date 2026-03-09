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
    SNIPPET_UPDATE = "snippet_update"


class ToastType(str, Enum):
    """Types of toast notifications broadcast via WebSocket."""
    FILE_UPLOADED = "file_uploaded"
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    REQUEST_CREATED = "request_created"
    REQUEST_FULFILLED = "request_fulfilled"


class RequestStatus(str, Enum):
    """Status of a file request."""
    PENDING = "pending"
    FULFILLED = "fulfilled"
    DISMISSED = "dismissed"
