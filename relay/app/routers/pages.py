"""Relay-served SPA shell for account pages.

Serves the existing client bundle's index.html at relay-root routes
(/login, /signup, /admin, /403). Assets are mounted at /assets by the
app factory. When the bundle is absent (dev/test), a minimal placeholder
is returned so the routes still resolve.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["pages"])

_CLIENT_DIST = Path(__file__).resolve().parents[3] / "client" / "dist"
_INDEX = _CLIENT_DIST / "index.html"

_PLACEHOLDER = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Network File Server</title></head>"
    "<body><div id='root'></div>"
    "<script type='module' src='/assets/index.js'></script>"
    "</body></html>"
)

_PAGE_PATHS = ("/login", "/signup", "/admin", "/403")


def _shell():
    if _INDEX.exists():
        return FileResponse(str(_INDEX), media_type="text/html")
    return HTMLResponse(_PLACEHOLDER)


@router.get("/login")
async def login_page():
    return _shell()


@router.get("/signup")
async def signup_page():
    return _shell()


@router.get("/admin")
async def admin_page():
    return _shell()


@router.get("/403")
async def forbidden_page():
    return _shell()
