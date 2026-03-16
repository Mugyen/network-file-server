"""Landing page router — serves the mount code entry page."""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

_template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))

router = APIRouter()


@router.get("/")
async def landing_page(request: Request, code: str = Query("")) -> RedirectResponse:
    """Serve landing page or redirect to mount URL.

    If `code` query param is non-empty, redirect 302 to /m/{code}/.
    Otherwise render the landing page template.
    """
    if code:
        return RedirectResponse(url=f"/m/{code}/", status_code=302)
    return templates.TemplateResponse(request, "landing.html")
