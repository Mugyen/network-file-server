"""Access-policy decision model + proxy enforcement."""

import time

import httpx
import pytest
from httpx import AsyncClient

from accounts import (
    AccessMode,
    Role,
    SqliteAccountStore,
    SubjectType,
    hash_password,
)
from relay.app.exceptions import AccessDeniedError, AuthenticationRequiredError
from relay.app.services.access_policy import authorize
from relay.app.services.account_store import set_account_store
from relay.app.services.mount_registry import PolicyEntry
from relay.app.services.session import RelaySession, SessionIdentity, set_relay_session
from relay.app.services.sqlite_registry import SqliteMountRegistry


@pytest.fixture
async def policy_env():
    registry = await SqliteMountRegistry.create(":memory:")
    store = await SqliteAccountStore.create(":memory:")
    set_account_store(store)
    session = RelaySession("secret")
    set_relay_session(session)
    yield registry, store, session
    set_account_store(None)
    set_relay_session(None)
    await store.close()
    await registry.close()


async def _register(registry, code: str) -> None:
    await registry.register(
        code, None, agent_ip="127.0.0.1", created_at=time.time(), expires_at=None
    )


def _id(user) -> SessionIdentity:
    return SessionIdentity(user_id=user.id, username=user.username)


async def test_open_mount_allows_anonymous(policy_env):
    registry, _store, _s = policy_env
    await _register(registry, "open1")
    await registry.set_owner_policy("open1", None, AccessMode.OPEN, False, [])
    decision = await authorize(registry, "open1", None)
    assert decision.identified is False


async def test_legacy_mount_without_policy_fails_open(policy_env):
    registry, _store, _s = policy_env
    decision = await authorize(registry, "nonexistent", None)
    assert decision.identified is False


async def test_restricted_no_password_anon_requires_auth(policy_env):
    registry, _store, _s = policy_env
    await _register(registry, "r1")
    await registry.set_owner_policy("r1", 1, AccessMode.RESTRICTED, False, [])
    with pytest.raises(AuthenticationRequiredError):
        await authorize(registry, "r1", None)


async def test_restricted_no_password_logged_in_not_allowed_denied(policy_env):
    registry, store, _s = policy_env
    user = await store.create_user("eve", hash_password("pw"), None)
    await _register(registry, "r2")
    await registry.set_owner_policy("r2", 1, AccessMode.RESTRICTED, False, [])
    with pytest.raises(AccessDeniedError):
        await authorize(registry, "r2", _id(user))


async def test_restricted_with_password_falls_through_for_anon(policy_env):
    registry, _store, _s = policy_env
    await _register(registry, "r3")
    await registry.set_owner_policy("r3", 1, AccessMode.RESTRICTED, True, [])
    decision = await authorize(registry, "r3", None)
    assert decision.identified is False  # server password will challenge


async def test_allowlisted_user_identified_with_role(policy_env):
    registry, store, _s = policy_env
    user = await store.create_user("alice", hash_password("pw"), None)
    await _register(registry, "r4")
    await registry.set_owner_policy(
        "r4", 1, AccessMode.RESTRICTED, False,
        [PolicyEntry(SubjectType.USER, user.id, Role.WRITE)],
    )
    decision = await authorize(registry, "r4", _id(user))
    assert decision.identified is True
    assert decision.username == "alice"
    assert decision.role is Role.WRITE


async def test_allowlisted_via_nested_group(policy_env):
    registry, store, _s = policy_env
    user = await store.create_user("bob", hash_password("pw"), None)
    org = await store.create_group("org")
    team = await store.create_group("team")
    await store.add_member(org.id, SubjectType.GROUP, team.id)
    await store.add_member(team.id, SubjectType.USER, user.id)
    await _register(registry, "r5")
    await registry.set_owner_policy(
        "r5", 1, AccessMode.RESTRICTED, False,
        [PolicyEntry(SubjectType.GROUP, org.id, Role.READ)],
    )
    decision = await authorize(registry, "r5", _id(user))
    assert decision.identified is True
    assert decision.role is Role.READ


async def test_highest_role_wins_on_multiple_matches(policy_env):
    registry, store, _s = policy_env
    user = await store.create_user("carol", hash_password("pw"), None)
    grp = await store.create_group("g")
    await store.add_member(grp.id, SubjectType.USER, user.id)
    await _register(registry, "r6")
    await registry.set_owner_policy(
        "r6", 1, AccessMode.RESTRICTED, False,
        [
            PolicyEntry(SubjectType.USER, user.id, Role.READ),
            PolicyEntry(SubjectType.GROUP, grp.id, Role.WRITE),
        ],
    )
    decision = await authorize(registry, "r6", _id(user))
    assert decision.role is Role.WRITE


# --- Proxy-level enforcement -------------------------------------------------


@pytest.fixture
async def proxy_env(relay_app, account_store, relay_session):
    """relay_app + accounts wired; returns (client, registry, store, session)."""
    from relay.app.services.mount_registry import get_registry

    registry = get_registry()
    transport = httpx.ASGITransport(app=relay_app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        yield client, registry, account_store, relay_session


async def test_proxy_restricted_no_pw_anon_redirects_html(proxy_env, mock_connection):
    client, registry, _store, _s = proxy_env
    await registry.register(
        "secretm", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy(
        "secretm", 1, AccessMode.RESTRICTED, False, []
    )
    r = await client.get(
        "/m/secretm/index.html",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].startswith("/login?next=")


async def test_proxy_restricted_no_pw_anon_json_401(proxy_env, mock_connection):
    client, registry, _store, _s = proxy_env
    await registry.register(
        "secretj", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy(
        "secretj", 1, AccessMode.RESTRICTED, False, []
    )
    r = await client.get("/m/secretj/api/files", headers={"accept": "application/json"})
    assert r.status_code == 401


async def test_proxy_allowlisted_user_passes_through(proxy_env, mock_connection):
    client, registry, store, session = proxy_env
    user = await store.create_user("dave", hash_password("pw"), None)
    await registry.register(
        "okm", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy(
        "okm", user.id, AccessMode.RESTRICTED, False,
        [PolicyEntry(SubjectType.USER, user.id, Role.READ)],
    )
    token = session.issue(user.id, user.username)
    r = await client.get(
        "/m/okm/file.txt",
        cookies={"wfs_session": token},
    )
    # MockTunnelConnection returns a 200 text/plain body.
    assert r.status_code == 200
    assert r.text == "hello world"


async def test_proxy_open_mount_anonymous_passes(proxy_env, mock_connection):
    client, registry, _store, _s = proxy_env
    await registry.register(
        "openpm", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy("openpm", None, AccessMode.OPEN, False, [])
    r = await client.get("/m/openpm/file.txt")
    assert r.status_code == 200


async def test_proxy_strips_spoofed_wfs_headers(proxy_env, mock_connection):
    client, registry, _store, _s = proxy_env
    await registry.register(
        "spoofm", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy("spoofm", None, AccessMode.OPEN, False, [])
    await client.get(
        "/m/spoofm/file.txt",
        headers={"x-wfs-role": "write", "x-wfs-user": "attacker",
                 "x-wfs-auth-bypass": "1"},
    )
    fwd = mock_connection.sent_opens[-1][1]["headers"]
    lowered = {k.lower() for k in fwd}
    assert "x-wfs-role" not in lowered
    assert "x-wfs-user" not in lowered
    assert "x-wfs-auth-bypass" not in lowered


async def test_proxy_injects_identity_for_allowlisted(proxy_env, mock_connection):
    client, registry, store, session = proxy_env
    user = await store.create_user("ivy", hash_password("pw"), None)
    await registry.register(
        "injm", mock_connection, agent_ip="127.0.0.1",
        created_at=time.time(), expires_at=None,
    )
    await registry.set_owner_policy(
        "injm", user.id, AccessMode.RESTRICTED, False,
        [PolicyEntry(SubjectType.USER, user.id, Role.WRITE)],
    )
    token = session.issue(user.id, user.username)
    await client.get(
        "/m/injm/file.txt",
        cookies={"wfs_session": token},
        headers={"x-wfs-role": "read"},  # spoof attempt — must be overridden
    )
    fwd = {k.lower(): v for k, v in mock_connection.sent_opens[-1][1]["headers"].items()}
    assert fwd["x-wfs-user"] == "ivy"
    assert fwd["x-wfs-role"] == "write"
    assert fwd["x-wfs-auth-bypass"] == "1"
