"""FastAPI dependencies for read-only write blocking and receive mode API restriction.

These are used as route dependencies via Depends() to enforce access control
at the endpoint level.
"""

from server.app.config import get_server_config
from server.app.exceptions import AccessDeniedError, ReadOnlyError


def require_write_access() -> None:
    """Raise ReadOnlyError if server is in read-only mode.

    Use as: dependencies=[Depends(require_write_access)] on write endpoints.
    """
    config = get_server_config()
    if config.read_only:
        raise ReadOnlyError("write operation")


def require_full_access() -> None:
    """Raise AccessDeniedError if server is in receive mode.

    Use as: dependencies=[Depends(require_full_access)] on endpoints
    that should not be accessible in receive mode.
    """
    config = get_server_config()
    if config.receive:
        raise AccessDeniedError("Access denied in receive mode")
