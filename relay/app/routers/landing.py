"""Landing page router — serves the mount code entry page."""

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from relay.app.config import get_config

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
    config = get_config()
    og_image_url = str(request.base_url) + "static/og-image.png"
    return templates.TemplateResponse(request, "landing.html", {
        "og_image_url": og_image_url,
        "github_url": "https://github.com/RahulDas-dev/network-file-server",
        "dropbox_url": f"/m/{config.dropbox_code}/",
    })
