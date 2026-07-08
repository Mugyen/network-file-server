"""RECEIVE role: upload + see/download only own uploads."""

import io
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.config import ServerConfig
from server.app.main import create_app
from shared.identity_sig import IDENTITY_SIG_HEADER, sign_identity

_SECRET = "receive-test-secret"


def _mount_app(folder: Path):
    config = ServerConfig(
        shared_folder=folder,
        port=8000,
        password_hash=None,
        read_only=False,
        receive=False,
        mount_code="ABC123",
        relay_url="https://relay.example.com",
        identity_secret=_SECRET,
    )
    return create_app(config)


async def _client(app):
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    )


def _recv(user: str) -> dict:
    """Signed RECEIVE-role identity headers as the relay would inject them."""
    return {
        "x-wfs-role": "receive",
        "x-wfs-user": user,
        "x-wfs-auth-bypass": "1",
        IDENTITY_SIG_HEADER: sign_identity(_SECRET, user, "receive", True),
    }


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    # Subdirectory of tmp_path so the upload-index DB at
    # shared_folder.parent / ".wfs_data" is unique per test.
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "preexisting.txt").write_text("old")
    return shared


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


async def test_receive_user_zip_own_ok_others_404(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        await _upload(c, "bob1.txt", _recv("bob"))
        own = await c.post(
            "/api/files/download-zip",
            json={"paths": ["alice1.txt"]},
            headers=_recv("alice"),
        )
        other = await c.post(
            "/api/files/download-zip",
            json={"paths": ["alice1.txt", "bob1.txt"]},
            headers=_recv("alice"),
        )
        pre = await c.post(
            "/api/files/download-zip",
            json={"paths": ["preexisting.txt"]},
            headers=_recv("alice"),
        )
    assert own.status_code == 200
    assert other.status_code == 404
    assert pre.status_code == 404


async def test_receive_user_share_management_blocked(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        create = await c.post(
            "/api/shares",
            json={"file_path": "preexisting.txt", "ttl": 3600},
            headers=_recv("alice"),
        )
        listing = await c.get("/api/shares", headers=_recv("alice"))
        revoke = await c.delete("/api/shares/fake-token", headers=_recv("alice"))
    assert create.status_code == 403
    assert listing.status_code == 403
    assert revoke.status_code == 403


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


async def test_receive_state_store_hidden_from_listing(folder):
    app = _mount_app(folder)
    async with await _client(app) as c:
        await _upload(c, "alice1.txt", _recv("alice"))
        r = await c.get(
            "/api/files",
            headers={"x-wfs-role": "write", "x-wfs-user": "admin"},
        )
    names = {e["name"] for e in r.json()["entries"]}
    assert "alice1.txt" in names
    assert "preexisting.txt" in names
    assert all(not name.startswith(".wfs_") for name in names)
