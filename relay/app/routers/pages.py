"""Relay-served SPA shell for account pages.

Serves the existing client bundle's index.html at relay-root routes
(/login, /signup, /admin, /403). Assets are mounted at /assets by the
app factory. When the bundle is absent (dev/test), the shared placeholder
shell is returned so the routes still resolve (see ``shared.spa``).
"""

from fastapi import APIRouter, Response

from shared.paths import repo_root
from shared.spa import spa_shell_response

router = APIRouter(tags=["pages"])

_INDEX = repo_root() / "client" / "dist" / "index.html"


def _shell() -> Response:
    return spa_shell_response(_INDEX)


@router.get("/login")
async def login_page() -> Response:
    return _shell()


@router.get("/signup")
async def signup_page() -> Response:
    return _shell()


@router.get("/admin")
async def admin_page() -> Response:
    return _shell()


@router.get("/403")
async def forbidden_page() -> Response:
    return _shell()
