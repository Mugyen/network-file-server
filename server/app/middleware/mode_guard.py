"""FastAPI dependencies for read-only write blocking and receive mode API restriction.

These are used as route dependencies via Depends() to enforce access control
at the endpoint level.
"""

from fastapi import Request

from accounts import Role
from server.app.exceptions import AccessDeniedError, ReadOnlyError
from server.app.services.relay_identity import trusted_role, trusted_user


def require_write_access(request: Request) -> None:
    """Allow writes for WRITE and RECEIVE roles; block READ.

    RECEIVE may upload (it passes here); other destructive endpoints also
    depend on require_full_access, which blocks RECEIVE. With no relay
    role the global read-only flag applies (password / LAN — unchanged).

    Use as: dependencies=[Depends(require_write_access)] on write endpoints.
    """
    config = request.app.state.config
    role = trusted_role(config, request.headers)
    if role is not None:
        if role is Role.READ:
            raise ReadOnlyError("write operation")
        return
    if config.read_only:
        raise ReadOnlyError("write operation")


def require_full_access(request: Request) -> None:
    """Block RECEIVE entirely (rename/delete/folders/clipboard/share/...).

    RECEIVE users get an upload + own-uploads view only; everything gated
    by this dependency stays off-limits to them. With no relay role the
    global receive flag applies (unchanged).

    Use as: dependencies=[Depends(require_full_access)] on endpoints
    that should not be accessible in receive mode.
    """
    config = request.app.state.config
    role = trusted_role(config, request.headers)
    if role is not None:
        if role is Role.RECEIVE:
            raise AccessDeniedError("Access denied in receive mode")
        return
    if config.receive:
        raise AccessDeniedError("Access denied in receive mode")


def require_browse_access(request: Request) -> None:
    """Allow READ/WRITE/RECEIVE to reach browse endpoints.

    RECEIVE is allowed through here but the endpoint MUST filter results
    to the user's own uploads (see receive_scope_user). With no relay
    role the global receive flag applies (LAN/password drop box stays
    upload-only — unchanged).

    Use on list/download/preview/search/zip endpoints.
    """
    config = request.app.state.config
    role = trusted_role(config, request.headers)
    if role is not None:
        return
    if config.receive:
        raise AccessDeniedError("Access denied in receive mode")


def receive_scope_user(request: Request) -> str | None:
    """Username to scope browse results to, or None for unrestricted.

    Returns the trusted username only when the relay role is RECEIVE;
    callers filter list/download/preview/search/zip to these uploads.
    """
    config = request.app.state.config
    if trusted_role(config, request.headers) is not Role.RECEIVE:
        return None
    return trusted_user(config, request.headers)
