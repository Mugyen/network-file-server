"""Tests for auth middleware, login endpoint, and server-info extension."""

import pytest
from httpx import ASGITransport, AsyncClient

from server.tests.conftest import TEST_PASSWORD


@pytest.mark.anyio
async def test_unauthenticated_api_returns_401(
    async_client_with_password: AsyncClient,
) -> None:
    """GET /api/files without cookie on password-protected server returns 401."""
    response = await async_client_with_password.get("/api/files")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_unauthenticated_spa_serves_html(
    configured_app_with_password: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """GET / (SPA) without cookie on password-protected server returns 200.

    The SPA must load so the React LoginPage can render client-side.
    Auth gating only applies to /api/* paths.
    """
    transport = ASGITransport(app=configured_app_with_password)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")
        assert response.status_code == 200


@pytest.mark.anyio
async def test_server_info_exempt_from_auth(
    async_client_with_password: AsyncClient,
) -> None:
    """GET /api/server-info without cookie is accessible (exempt path)."""
    response = await async_client_with_password.get("/api/server-info")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_login_with_correct_password(
    async_client_with_password: AsyncClient,
) -> None:
    """POST /api/auth/login with correct password returns 200 and sets session cookie."""
    response = await async_client_with_password.post(
        "/api/auth/login",
        json={"password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Check session cookie is set
    assert "session" in response.cookies


@pytest.mark.anyio
async def test_login_with_wrong_password(
    async_client_with_password: AsyncClient,
) -> None:
    """POST /api/auth/login with wrong password returns 401 and no cookie."""
    response = await async_client_with_password.post(
        "/api/auth/login",
        json={"password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


@pytest.mark.anyio
async def test_login_with_empty_password(
    async_client_with_password: AsyncClient,
) -> None:
    """POST /api/auth/login with empty password returns 401."""
    response = await async_client_with_password.post(
        "/api/auth/login",
        json={"password": ""},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_authenticated_request_passes(
    async_client_with_password: AsyncClient,
) -> None:
    """GET /api/files with valid session cookie returns 200."""
    # Login first to get a cookie
    login_response = await async_client_with_password.post(
        "/api/auth/login",
        json={"password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    session_cookie = login_response.cookies["session"]

    # Use the session cookie
    response = await async_client_with_password.get(
        "/api/files",
        cookies={"session": session_cookie},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_tampered_cookie_returns_401(
    async_client_with_password: AsyncClient,
) -> None:
    """GET /api/files with tampered session cookie returns 401."""
    response = await async_client_with_password.get(
        "/api/files",
        cookies={"session": "tampered-invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_no_auth_middleware_without_password(
    async_client: AsyncClient,
) -> None:
    """Server without password has no auth middleware (all requests pass)."""
    response = await async_client.get("/api/files")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_server_info_returns_mode_fields(
    async_client: AsyncClient,
) -> None:
    """Server-info returns read_only, receive, password_required, hostname fields."""
    response = await async_client.get("/api/server-info")
    assert response.status_code == 200
    data = response.json()
    assert "read_only" in data
    assert "receive" in data
    assert "password_required" in data
    assert "hostname" in data
    assert data["read_only"] is False
    assert data["receive"] is False
    assert data["password_required"] is False
    assert isinstance(data["hostname"], str)


@pytest.mark.anyio
async def test_server_info_password_required_true(
    async_client_with_password: AsyncClient,
) -> None:
    """Server-info password_required is true when password set."""
    response = await async_client_with_password.get("/api/server-info")
    assert response.status_code == 200
    data = response.json()
    assert data["password_required"] is True


def test_websocket_without_cookie_on_protected_server(
    configured_app_with_password: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """WebSocket /ws without valid cookie on password-protected server is closed with 4001."""
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    client = TestClient(configured_app_with_password)
    with client.websocket_connect("/ws?device_name=test") as ws:
        # Server should accept then immediately close with 4001
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
        assert exc_info.value.code == 4001


def test_websocket_with_valid_cookie_on_protected_server(
    configured_app_with_password: "FastAPI",  # type: ignore[name-defined]  # noqa: F821
) -> None:
    """WebSocket /ws with valid cookie on password-protected server connects successfully."""
    from starlette.testclient import TestClient

    token_service = configured_app_with_password.state.token_service
    valid_token = token_service.create_token()

    client = TestClient(configured_app_with_password, cookies={"session": valid_token})
    with client.websocket_connect("/ws?device_name=test") as ws:
        # Consume broadcast messages sent on connect (toast + device_count)
        ws.send_json({"type": "ping"})
        # Read messages until we get the pong response
        found_pong = False
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "pong":
                found_pong = True
                break
        assert found_pong, "Expected pong response from WebSocket"


@pytest.mark.anyio
async def test_auth_login_exempt_from_auth(
    async_client_with_password: AsyncClient,
) -> None:
    """POST /api/auth/login is exempt from auth middleware (accessible without cookie)."""
    # Even with wrong password, we should get 401 from the endpoint, not the middleware
    response = await async_client_with_password.post(
        "/api/auth/login",
        json={"password": "wrong"},
    )
    # We get 401 from the login endpoint itself, not from middleware blocking
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid password"
