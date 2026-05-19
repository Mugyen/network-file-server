"""RECEIVE role: upload + see/download only own uploads."""

import io
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig, set_server_config


def _mount_app(folder: Path):
    set_server_config(
        ServerConfig(
            shared_folder=folder,
            port=8000,
            password_hash=None,
            read_only=False,
            receive=False,
            mount_code="ABC123",
            relay_url="https://relay.example.com",
        )
    )
    from server.app.main import create_app

    return create_app()


async def _client(app):
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    )


def _recv(user: str) -> dict:
    return {"x-wfs-role": "receive", "x-wfs-user": user}


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "preexisting.txt").write_text("old")
    return tmp_path


async def _upload(client, name: str, headers: dict):
    return await client.post(
        "/api/files/upload",
        files={"files": (name, io.BytesIO(b"data"), "text/plain")},
        headers=headers,
    )


async def test_receive_user_can_upload(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        r = await _upload(c, "alice1.txt", _recv("alice"))
    assert r.status_code == 200
    assert (folder / "alice1.txt").exists()


async def test_receive_user_sees_only_own_uploads(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        await _upload(c, "bob1.txt", _recv("bob"))
        r = await c.get("/api/files", headers=_recv("alice"))
    names = {e["name"] for e in r.json()["entries"]}
    assert names == {"alice1.txt"}
    assert "preexisting.txt" not in names
    assert "bob1.txt" not in names


async def test_receive_user_download_own_ok_others_404(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        await _upload(c, "bob1.txt", _recv("bob"))
        own = await c.get(
            "/api/files/download", params={"path": "alice1.txt"},
            headers=_recv("alice"),
        )
        other = await c.get(
            "/api/files/download", params={"path": "bob1.txt"},
            headers=_recv("alice"),
        )
        pre = await c.get(
            "/api/files/download", params={"path": "preexisting.txt"},
            headers=_recv("alice"),
        )
    assert own.status_code == 200
    assert other.status_code == 404
    assert pre.status_code == 404


async def test_receive_preview_others_404(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "bob1.txt", _recv("bob"))
        r = await c.get(
            "/api/files/preview", params={"path": "bob1.txt"},
            headers=_recv("alice"),
        )
    assert r.status_code == 404


async def test_receive_search_returns_empty(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        r = await c.get(
            "/api/files/search", params={"q": "alice"}, headers=_recv("alice")
        )
    assert r.json()["entries"] == []


async def test_write_role_sees_everything(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        r = await c.get(
            "/api/files",
            headers={"x-wfs-role": "write", "x-wfs-user": "admin"},
        )
    names = {e["name"] for e in r.json()["entries"]}
    assert "preexisting.txt" in names
    assert "alice1.txt" in names


async def test_receive_blocked_from_destructive_ops(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        r = await c.post(
            "/api/folders",
            json={"parent_path": "", "name": "x"},
            headers=_recv("alice"),
        )
    assert r.status_code == 403


async def test_index_sidecar_hidden_from_listing(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        r = await c.get(
            "/api/files",
            headers={"x-wfs-role": "write", "x-wfs-user": "admin"},
        )
    names = {e["name"] for e in r.json()["entries"]}
    assert ".wfs_upload_index.json" not in names
