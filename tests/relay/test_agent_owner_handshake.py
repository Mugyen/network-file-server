"""Relay-side agent_auth handshake: owner binding, policy, restricted gating."""

import json
import os
from unittest.mock import patch

import httpx
import pytest
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from accounts import AccessMode, Role, SqliteAccountStore, SubjectType, hash_password
from relay.app.main import create_relay_app
from relay.app.services.account_store import set_account_store
from relay.app.services.mount_registry import get_registry
from relay.app.services.session import RelaySession, set_relay_session
from tests.relay.conftest import _setup_in_memory_registry

pytestmark = pytest.mark.anyio


@pytest.fixture
async def owner_app():
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        app = create_relay_app()
    from relay.app.routers.agent_ws import reset_mount_reg_limiter

    reset_mount_reg_limiter()
    registry = await _setup_in_memory_registry()
    store = await SqliteAccountStore.create(":memory:")
    set_account_store(store)
    session = RelaySession("test-relay-secret")
    set_relay_session(session)
    yield app, registry, store, session
    set_account_store(None)
    set_relay_session(None)
    await store.close()
    await registry.close()


async def _handshake(app, path: str, auth_msg: dict) -> dict:
    transport = ASGIWebSocketTransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with aconnect_ws(
            f"http://testserver{path}",
            client,
            keepalive_ping_interval_seconds=None,
            keepalive_ping_timeout_seconds=None,
        ) as ws:
            await ws.send_text(json.dumps(auth_msg))
            return json.loads(await ws.receive_text())


async def test_anonymous_open_handshake(owner_app):
    app, registry, _store, _session = owner_app
    msg = await _handshake(
        app,
        "/agent/ws?code=openm",
        {"type": "agent_auth", "token": None, "access_mode": "open",
         "has_password": False, "allowlist": []},
    )
    assert msg["type"] == "mount_registered"
    assert msg["owner"] is None
    policy = await registry.get_policy("openm")
    assert policy.access_mode is AccessMode.OPEN
    assert policy.owner_user_id is None
    assert policy.entries == ()


async def test_restricted_owner_handshake_persists_policy(owner_app):
    app, registry, store, session = owner_app
    owner = await store.create_user("alice", hash_password("pw"), None)
    member = await store.create_user("bob", hash_password("pw"), None)
    grp = await store.create_group("eng")
    token = session.issue_agent_owner_token(owner.id)

    msg = await _handshake(
        app,
        "/agent/ws?code=secret1",
        {
            "type": "agent_auth",
            "token": token,
            "access_mode": "restricted",
            "has_password": True,
            "allowlist": [
                {"subject_type": "user", "subject_ref": "bob", "role": "write"},
                {"subject_type": "group", "subject_ref": "eng", "role": "read"},
            ],
        },
    )
    assert msg["type"] == "mount_registered"
    assert msg["owner"] == "alice"

    policy = await registry.get_policy("secret1")
    assert policy.access_mode is AccessMode.RESTRICTED
    assert policy.owner_user_id == owner.id
    assert policy.has_password is True
    by_subject = {(e.subject_type, e.subject_id): e.role for e in policy.entries}
    assert by_subject[(SubjectType.USER, member.id)] is Role.WRITE
    assert by_subject[(SubjectType.GROUP, grp.id)] is Role.READ


async def test_restricted_without_token_rejected(owner_app):
    app, _registry, _store, _session = owner_app
    msg = await _handshake(
        app,
        "/agent/ws",
        {"type": "agent_auth", "token": None, "access_mode": "restricted",
         "has_password": False, "allowlist": []},
    )
    assert msg["type"] == "error"
    assert "restricted" in msg["error"]


async def test_invalid_owner_token_rejected(owner_app):
    app, _registry, _store, _session = owner_app
    msg = await _handshake(
        app,
        "/agent/ws",
        {"type": "agent_auth", "token": "garbage", "access_mode": "restricted",
         "has_password": False, "allowlist": []},
    )
    assert msg["type"] == "error"
    assert "owner token" in msg["error"]


async def test_unknown_allowlist_ref_rejected(owner_app):
    app, _registry, store, session = owner_app
    owner = await store.create_user("alice", hash_password("pw"), None)
    token = session.issue_agent_owner_token(owner.id)
    msg = await _handshake(
        app,
        "/agent/ws",
        {
            "type": "agent_auth",
            "token": token,
            "access_mode": "restricted",
            "has_password": False,
            "allowlist": [
                {"subject_type": "user", "subject_ref": "ghost", "role": "read"}
            ],
        },
    )
    assert msg["type"] == "error"
    assert "ghost" in msg["error"]


async def test_missing_agent_auth_frame_rejected(owner_app):
    app, _registry, _store, _session = owner_app
    msg = await _handshake(
        app, "/agent/ws", {"type": "not_agent_auth"}
    )
    assert msg["type"] == "error"
    assert "agent_auth" in msg["error"]
