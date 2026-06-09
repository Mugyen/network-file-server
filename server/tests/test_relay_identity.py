"""Trusted relay-identity headers: per-request role, auth-bypass, spoof boundary."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig
from server.app.main import create_app
from server.app.services.auth_service import hash_password


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
    return create_app(config)


async def _client(app):
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    # Subdirectory of tmp_path so the app's data dir at
    # shared_folder.parent / ".wfs_data" is unique per test.
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "f.txt").write_text("hi")
    return shared


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


async def test_mount_mode_receive_role_browse_is_scoped_not_blocked(folder):
    # RECEIVE may browse, but the listing is scoped to the user's own
    # uploads (empty here — nothing uploaded by this user).
    app = _app(folder, password=False, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.get(
            "/api/files",
            headers={"x-wfs-role": "receive", "x-wfs-user": "nobody"},
        )
    assert r.status_code == 200
    assert r.json()["entries"] == []


async def test_mount_mode_receive_role_blocks_destructive(folder):
    app = _app(folder, password=False, read_only=False, receive=False, mount=True)
    async with await _client(app) as c:
        r = await c.delete(
            "/api/files",
            params={},
            headers={"x-wfs-role": "receive", "x-wfs-user": "nobody"},
        )
    # DELETE has require_full_access -> RECEIVE blocked (403/422 if no body).
    assert r.status_code in (403, 422)


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
