"""SPA shell responses for apps that serve the built client bundle.

Both the server app (catch-all route) and the relay (account pages) serve
``client/dist/index.html``. When the bundle is absent (dev/CI without a
client build), a minimal placeholder shell is served instead so SPA routes
still resolve with 200 rather than 404.
"""

from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse

# Mirrors client/index.html: a root div plus module script. Renders blank
# without the bundle, but lets SPA routes resolve in environments where the
# client has not been built.
SPA_PLACEHOLDER_HTML = (
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<title>Network File Server</title></head>"
    "<body><div id='root'></div>"
    "<script type='module' src='/assets/index.js'></script>"
    "</body></html>"
)


def spa_shell_response(index_html: Path) -> FileResponse | HTMLResponse:
    """Serve the built SPA's index.html, or the placeholder when absent.

    Args:
        index_html: Path to the built SPA's ``index.html``. A missing file is
            an expected state (no client build), not an error.

    Returns:
        ``FileResponse`` for the built index.html, or ``HTMLResponse`` with
        the placeholder shell when the bundle has not been built.
    """
    if index_html.is_file():
        return FileResponse(str(index_html), media_type="text/html")
    return HTMLResponse(SPA_PLACEHOLDER_HTML)
