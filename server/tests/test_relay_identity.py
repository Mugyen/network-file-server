"""Trusted relay-identity headers: per-request role, auth-bypass, spoof boundary."""

import secrets
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config
from server.app.services.auth_service import (
    AuthTokenService,
    hash_password,
    set_token_service,
)


def _app(folder: Path, *, password: bool, read_only: bool, receive: bool, mount: bool):
    config = ServerConfig(
        shared_folder=folder,
        port=8000,
        password_hash=hash_password("pw") if password else None,
        read_only=read_only,
        receive=receive,
        mount_code="ABC123" if mount else None,
        relay_url="https://relay.example.com" if mount else None,
    )
    set_server_config(config)
    if password:
        set_token_service(AuthTokenService(secrets.token_hex(32)))
    from server.app.main import create_app

    return create_app()


async def _client(app):
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "f.txt").write_text("hi")
    return tmp_path


async def test_mount_mode_write_role_allows_write(folder):
    app = _app(folder, password=False, read_only=True, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.post(
            "/api/folders",
            json={"parent_path": "", "name": "newdir"},
            headers={"x-wfs-role": "write"},
        )
    assert r.status_code == 201


async def test_mount_mode_read_role_blocks_write(folder):
    app = _app(folder, password=False, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.post(
            "/api/folders",
            json={"parent_path": "", "name": "nope"},
            headers={"x-wfs-role": "read"},
        )
    assert r.status_code == 403


async def test_mount_mode_receive_role_blocks_browse(folder):
    app = _app(folder, password=False, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.get("/api/files", headers={"x-wfs-role": "receive"})
    assert r.status_code == 403


async def test_lan_mode_ignores_spoofed_role_header(folder):
    # Read-only LAN server (mount_code None): a spoofed write role MUST NOT
    # bypass read-only enforcement.
    app = _app(folder, password=False, read_only=True, receive=False, mount=False)
    async with await _client(app) as c:
        r = await c.post(
            "/api/folders",
            json={"parent_path": "", "name": "evil"},
            headers={"x-wfs-role": "write"},
        )
    assert r.status_code == 403


async def test_mount_mode_auth_bypass_skips_password(folder):
    app = _app(folder, password=True, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.get("/api/files", headers={"x-wfs-auth-bypass": "1"})
    assert r.status_code == 200


async def test_lan_mode_ignores_spoofed_auth_bypass(folder):
    # Password LAN server: spoofed bypass header must NOT skip the cookie gate.
    app = _app(folder, password=True, read_only=False, receive=False, mount=False)
    async with await _client(app) as c:
        r = await c.get("/api/files", headers={"x-wfs-auth-bypass": "1"})
    assert r.status_code == 401


async def test_server_info_exposes_identity_in_mount_mode(folder):
    app = _app(folder, password=False, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.get(
            "/api/server-info",
            headers={"x-wfs-user": "alice", "x-wfs-role": "write"},
        )
    body = r.json()
    assert body["current_user"] == "alice"
    assert body["current_role"] == "write"
