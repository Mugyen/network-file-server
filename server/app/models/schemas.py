from pydantic import BaseModel

from server.app.models.enums import FileType


class FileEntry(BaseModel):
    name: str
    size: int
    size_display: str
    type: FileType
    modified: str


class DirectoryListing(BaseModel):
    path: str
    entries: list[FileEntry]


class ServerInfo(BaseModel):
    """Server information including IP, port, URL, and QR code data."""

    ip: str
    port: int
    url: str
    qr_svg: str
    all_ips: list[str]
