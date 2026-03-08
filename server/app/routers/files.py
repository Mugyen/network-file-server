"""Files API router.

Provides endpoints for listing directory contents.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from server.app.config import get_server_config
from server.app.exceptions import PathTraversalError
from server.app.services.file_service import list_directory

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
def get_files(path: str = Query("")) -> dict:
    """List files in the shared folder.

    Query parameter 'path' specifies a relative subdirectory.
    Empty string means root of the shared folder.
    """
    config = get_server_config()
    try:
        listing = list_directory(config.shared_folder, path)
        return listing.model_dump()
    except PathTraversalError as exc:
        return JSONResponse(
            status_code=403,
            content={"error": str(exc)},
        )
    except FileNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={"error": str(exc)},
        )
