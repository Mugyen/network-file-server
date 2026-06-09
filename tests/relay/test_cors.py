"""Tests for conditional CORS configuration in the relay app.

Verifies that CORS is configured differently based on RELAY_ENV:
- development: wildcard origins, no credentials
- production: explicit origins only, with credentials
"""


import pytest
from httpx import ASGITransport, AsyncClient

from relay.app.main import create_relay_app


def _make_client(app: object) -> AsyncClient:
    """Create an AsyncClient from an ASGI app. Not a context manager -- caller closes."""
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_cors_wildcard_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """In development mode (default), CORS allows any origin."""
    monkeypatch.delenv("RELAY_ENV", raising=False)
    monkeypatch.delenv("RELAY_ALLOWED_ORIGINS", raising=False)

    app = create_relay_app()
    async with _make_client(app) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") == "*"


@pytest.mark.anyio
async def test_cors_rejects_unlisted_origin_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In production, a preflight from an unlisted origin gets no ACAO header."""
    monkeypatch.setenv("RELAY_ENV", "production")
    monkeypatch.setenv("RELAY_ALLOWED_ORIGINS", "https://example.com")

    app = create_relay_app()
    async with _make_client(app) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        acao = response.headers.get("access-control-allow-origin")
        # Starlette CORS returns 400 or omits the header for disallowed origins
        assert acao is None or acao != "https://evil.com"


@pytest.mark.anyio
async def test_cors_allows_listed_origin_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In production, a preflight from a listed origin returns that origin."""
    monkeypatch.setenv("RELAY_ENV", "production")
    monkeypatch.setenv("RELAY_ALLOWED_ORIGINS", "https://example.com")

    app = create_relay_app()
    async with _make_client(app) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            response.headers.get("access-control-allow-origin") == "https://example.com"
        )


@pytest.mark.anyio
async def test_cors_credentials_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production CORS includes Access-Control-Allow-Credentials: true."""
    monkeypatch.setenv("RELAY_ENV", "production")
    monkeypatch.setenv("RELAY_ALLOWED_ORIGINS", "https://example.com")

    app = create_relay_app()
    async with _make_client(app) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.anyio
async def test_cors_multiple_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    """RELAY_ALLOWED_ORIGINS with multiple comma-separated origins allows both."""
    monkeypatch.setenv("RELAY_ENV", "production")
    monkeypatch.setenv("RELAY_ALLOWED_ORIGINS", "https://a.com,https://b.com")

    app = create_relay_app()
    async with _make_client(app) as client:
        # Check first origin
        resp_a = await client.options(
            "/health",
            headers={
                "Origin": "https://a.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_a.headers.get("access-control-allow-origin") == "https://a.com"

        # Check second origin
        resp_b = await client.options(
            "/health",
            headers={
                "Origin": "https://b.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp_b.headers.get("access-control-allow-origin") == "https://b.com"


def test_missing_origins_raises_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RELAY_ENV=production with no RELAY_ALLOWED_ORIGINS raises ValueError."""
    monkeypatch.setenv("RELAY_ENV", "production")
    monkeypatch.delenv("RELAY_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(ValueError, match="RELAY_ALLOWED_ORIGINS"):
        create_relay_app()


@pytest.mark.anyio
async def test_dev_cors_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev CORS does not send Access-Control-Allow-Credentials (wildcard + credentials is invalid)."""
    monkeypatch.delenv("RELAY_ENV", raising=False)
    monkeypatch.delenv("RELAY_ALLOWED_ORIGINS", raising=False)

    app = create_relay_app()
    async with _make_client(app) as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Credentials should NOT be set in dev wildcard mode
        cred = response.headers.get("access-control-allow-credentials")
        assert cred is None or cred != "true"
