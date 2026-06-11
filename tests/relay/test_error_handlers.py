"""Tests for the relay's central domain-exception -> HTTP mapping."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from relay.app.error_handlers import register_exception_handlers
from relay.app.exceptions import (
    AccessDeniedError,
    AccessRequestNotFoundError,
    AuthenticationRequiredError,
    InvalidSessionError,
    MountExpiredError,
    MountNotFoundError,
    MountOfflineError,
)

_CASES: list[tuple[Exception, int]] = [
    (MountNotFoundError("abc123"), 404),
    (MountOfflineError("abc123"), 503),
    (MountExpiredError("abc123"), 410),
    (AccessRequestNotFoundError(7), 404),
    (InvalidSessionError("expired"), 401),
    (AuthenticationRequiredError("abc123"), 401),
    (AccessDeniedError("abc123", "mallory"), 403),
]


def _app_raising(exc: Exception) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("exc,status", _CASES, ids=[type(e).__name__ for e, _ in _CASES])
async def test_exception_maps_to_status(exc: Exception, status: int) -> None:
    """Each relay domain exception maps to its documented status."""
    transport = ASGITransport(app=_app_raising(exc))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/boom")
    assert resp.status_code == status
    assert "detail" in resp.json()


def test_register_rejects_non_app() -> None:
    """register_exception_handlers validates its input."""
    with pytest.raises(ValueError):
        register_exception_handlers(object())  # type: ignore[arg-type]
