"""Network File Server — public package interface.

External consumers (the relay embeds a server instance for its drop box and
reuses the file service for per-user storage) must import ONLY from this
module, never from server.app.* internals. This keeps the internal layout
free to change. Enforced by tests/relay/test_import_boundaries.py.

``create_app`` is exposed lazily (PEP 562) because importing
``server.app.main`` currently constructs a module-level app as a side
effect; the lazy hook avoids paying that on ``import server``.
"""

from typing import Any

from server.app.config import (
    ServerConfig,
    create_default_config,
)
from server.app.exceptions import (
    AccessDeniedError,
    FileConflictError,
    InvalidFileNameError,
    PathTraversalError,
    ReadOnlyError,
)
from server.app.models.enums import ConflictResolution
from server.app.models.schemas import DeleteRequest, DirectoryListing, UploadResult
from server.app.services.file_service import (
    delete_paths,
    download_file,
    list_directory,
    upload_file,
)
from server.app.services.file_ttl_provider import FileTtlProvider

__all__ = [
    # App factory (lazy — see __getattr__)
    "create_app",
    # Configuration
    "ServerConfig",
    "create_default_config",
    # Domain exceptions
    "AccessDeniedError",
    "FileConflictError",
    "InvalidFileNameError",
    "PathTraversalError",
    "ReadOnlyError",
    # Enums / schemas
    "ConflictResolution",
    "DeleteRequest",
    "DirectoryListing",
    "UploadResult",
    # Services
    "delete_paths",
    "download_file",
    "list_directory",
    "upload_file",
    # TTL provider seam (inject via app.state.file_ttl_provider)
    "FileTtlProvider",
]


def __getattr__(name: str) -> Any:
    if name == "create_app":
        from server.app.main import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
