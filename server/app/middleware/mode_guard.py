"""FastAPI dependencies for read-only write blocking and receive mode API restriction.

These are used as route dependencies via Depends() to enforce access control
at the endpoint level.
"""

from fastapi import Request

from accounts import Role
from server.app.config import get_server_config
from server.app.exceptions import AccessDeniedError, ReadOnlyError
from server.app.services.relay_identity import trusted_role


def require_write_access(request: Request) -> None:
    """Block writes for read-only mounts / non-WRITE relay roles.

    When the relay vouches for a user (trusted X-WFS-Role present), that
    per-request role decides. Otherwise the global read-only flag applies
    (password / LAN path — unchanged behaviour).

    Use as: dependencies=[Depends(require_write_access)] on write endpoints.
    """
    role = trusted_role(request.headers)
    if role is not None:
        if role is not Role.WRITE:
            raise ReadOnlyError("write operation")
        return
    if get_server_config().read_only:
        raise ReadOnlyError("write operation")


def require_full_access(request: Request) -> None:
    """Block browse/download for receive mounts / RECEIVE relay role.

    RECEIVE is upload-only at the API surface (same gate as the existing
    receive mode). Otherwise the global receive flag applies.

    Use as: dependencies=[Depends(require_full_access)] on endpoints
    that should not be accessible in receive mode.
    """
    role = trusted_role(request.headers)
    if role is not None:
        if role is Role.RECEIVE:
            raise AccessDeniedError("Access denied in receive mode")
        return
    if get_server_config().receive:
        raise AccessDeniedError("Access denied in receive mode")
