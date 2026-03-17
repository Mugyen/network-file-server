"""Rate limiting for the relay server — SlowAPI limiter, IP key function, 429 handler.

Uses SlowAPI with moving-window strategy and in-memory storage. The custom key
function extracts client IP from X-Forwarded-For (Cloud Run proxy) or falls
back to request.client.host.
"""

import logging
import re
from pathlib import Path

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates

logger = logging.getLogger("relay.ratelimit")

_template_dir = Path(__file__).resolve().parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_template_dir))

# Regex to extract seconds from rate limit strings like "300/minute", "5/hour"
_TIME_UNIT_SECONDS: dict[str, int] = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
}


def get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or fall back to direct connection.

    Matches the existing pattern at mount_proxy.py:85-88 and is used as the
    SlowAPI key function for per-IP rate limiting.

    Args:
        request: The incoming Starlette/FastAPI request.

    Returns:
        The client IP address as a string.

    Raises:
        ValueError: If neither X-Forwarded-For nor request.client is available.
    """
    forwarded: str | None = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    raise ValueError("Cannot determine client IP from request")


def _parse_retry_after(detail: str) -> int:
    """Extract retry-after seconds from a SlowAPI rate limit detail string.

    SlowAPI detail strings look like "Rate limit exceeded: 2 per 1 minute".
    We parse the time unit and return the corresponding seconds.

    Args:
        detail: The detail string from a RateLimitExceeded exception.

    Returns:
        Number of seconds to suggest waiting.
    """
    for unit, seconds in _TIME_UNIT_SECONDS.items():
        if unit in detail.lower():
            return seconds
    # Fallback: 60 seconds
    return 60


limiter = Limiter(
    key_func=get_client_ip,
    strategy="moving-window",
    headers_enabled=True,
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle 429 responses — styled HTML for browsers, JSON for API clients.

    Logs the rate-limited request at WARNING level with client IP and path
    for abuse monitoring in Cloud Logging.

    Args:
        request: The rate-limited request.
        exc: The RateLimitExceeded exception raised by SlowAPI.

    Returns:
        HTML TemplateResponse for browsers, JSONResponse for API clients.
    """
    retry_after: int = _parse_retry_after(str(exc.detail))

    try:
        client_ip: str = get_client_ip(request)
    except ValueError:
        client_ip = "unknown"

    logger.warning("Rate limited: client=%s path=%s", client_ip, request.url.path)

    accept: str = request.headers.get("accept", "")
    if "text/html" in accept:
        return _templates.TemplateResponse(
            request,
            "rate_limited.html",
            context={"retry_after": retry_after},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )
