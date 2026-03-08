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
