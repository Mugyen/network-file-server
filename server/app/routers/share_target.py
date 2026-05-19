"""PWA Web Share Target router.

Accepts files shared from the operating system's share sheet (Android,
ChromeOS) when the SPA is installed as a PWA. Bypasses the in-page file
picker entirely — useful on devices (some Realme/OPPO/Samsung builds)
where Chrome's file chooser is intercepted by an OEM media-only picker.

The route is registered under /api/share-upload so it inherits the existing
auth middleware. The manifest's share_target.action uses a relative URL
(``api/share-upload``) so it resolves correctly both at the SPA root and
under the relay's /m/{code}/ prefix.

After a successful upload the route returns a 303 redirect with
``Location: ../`` so the browser navigates back to the SPA root in both
standalone and relay-mounted deployments (relative resolution against
``/api/share-upload`` and ``/m/{code}/api/share-upload`` both produce the
correct root).
"""

from fastapi import APIRouter, Depends, Header, UploadFile
from fastapi.responses import RedirectResponse

from server.app.config import get_server_config
from server.app.exceptions import PathTraversalError
from server.app.middleware.mode_guard import require_write_access
from server.app.models.enums import ConflictResolution
from server.app.services.file_service import upload_file

router = APIRouter(prefix="/api", tags=["share-target"])


@router.post(
    "/share-upload",
    response_model=None,
    dependencies=[Depends(require_write_access)],
)
async def share_upload(
    files: list[UploadFile],
    x_device_name: str | None = Header(None),
) -> RedirectResponse:
    """Accept files shared via the PWA Web Share Target API.

    Stores each file at the root of the shared folder, auto-renaming on
    conflict so the share never fails. Returns a 303 redirect so the
    browser navigates back to the SPA after upload.

    Args:
        files: Multipart files posted by the share sheet. May be empty if
            the user shared a URL or text without a file attachment.
        x_device_name: Optional device-name header for upload attribution.

    Returns:
        303 RedirectResponse pointing at ``../`` (resolves to the SPA root
        from ``/api/share-upload`` and ``/m/{code}/api/share-upload``).

    Raises:
        ValueError: When the request contains no files at all.
    """
    if not isinstance(files, list):
        raise ValueError("files must be a list of UploadFile")

    if len(files) == 0:
        raise ValueError("share-upload requires at least one file")

    config = get_server_config()

    try:
        for upload in files:
            await upload_file(
                config.shared_folder,
                "",
                upload,
                ConflictResolution.RENAME,
            )
    except PathTraversalError as exc:
        raise ValueError(str(exc)) from exc

    # Relative redirect — works both at /api/share-upload and
    # /m/{code}/api/share-upload because the browser resolves Location
    # against the request URL.
    return RedirectResponse(url="../", status_code=303)
