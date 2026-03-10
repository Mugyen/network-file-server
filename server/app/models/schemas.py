from typing import Literal

from pydantic import BaseModel

from server.app.models.enums import FileType, RequestStatus, ShareTTL, ToastType


class FileEntry(BaseModel):
    name: str
    size: int
    size_display: str
    type: FileType
    modified: str


class DirectoryListing(BaseModel):
    path: str
    entries: list[FileEntry]


class SearchResult(BaseModel):
    """Result of a file search operation."""

    query: str
    path: str
    entries: list[FileEntry]


class ServerInfo(BaseModel):
    """Server information including IP, port, URL, QR code, and mode data."""

    ip: str
    port: int
    url: str
    qr_svg: str
    all_ips: list[str]
    read_only: bool
    receive: bool
    password_required: bool
    hostname: str


class UploadResult(BaseModel):
    """Result of a single file upload operation."""

    name: str
    size: int
    size_display: str
    skipped: bool


class RenameRequest(BaseModel):
    """Request body for renaming a file or folder."""

    path: str
    new_name: str


class DeleteRequest(BaseModel):
    """Request body for deleting one or more paths."""

    paths: list[str]


class CreateFolderRequest(BaseModel):
    """Request body for creating a new folder."""

    parent_path: str
    name: str


class DownloadZipRequest(BaseModel):
    """Request body for downloading multiple files as ZIP."""

    paths: list[str]


class ToastPayload(BaseModel):
    """WebSocket toast notification payload."""

    type: Literal["toast"]
    toast_type: ToastType
    message: str
    device_name: str
    timestamp: str


class DeviceCountPayload(BaseModel):
    """WebSocket device count update payload."""

    type: Literal["device_count"]
    count: int


class Snippet(BaseModel):
    """A clipboard snippet with title and content."""

    id: str
    title: str
    content: str
    created_at: str
    updated_at: str


class CreateSnippetRequest(BaseModel):
    """Request body for creating a new clipboard snippet."""

    title: str


class UpdateSnippetRequest(BaseModel):
    """Request body for updating snippet content."""

    content: str


class UpdateSnippetTitleRequest(BaseModel):
    """Request body for updating snippet title."""

    title: str


class FileRequest(BaseModel):
    """A file request that one device creates for others to fulfill."""

    id: str
    description: str
    requester_device_id: str
    requester_device_name: str
    status: RequestStatus
    created_at: str
    fulfilled_by_device_name: str | None
    fulfilled_file_name: str | None
    fulfilled_file_path: str | None
    fulfilled_at: str | None


class CreateFileRequestPayload(BaseModel):
    """Request body for creating a new file request."""

    description: str


class LoginRequest(BaseModel):
    """Request body for the login endpoint."""

    password: str


class CreateShareRequest(BaseModel):
    """Request body for creating a new share link."""

    file_path: str
    ttl: ShareTTL


class ShareLinkInfo(BaseModel):
    """Response model for a share link with metadata."""

    token: str
    file_path: str
    file_name: str
    created_at: str
    expires_at: str
    ttl_seconds: int
    share_url: str
