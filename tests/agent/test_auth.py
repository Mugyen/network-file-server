"""Agent owner auth helpers: allow-entry parsing + token fetch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accounts import Role, SubjectType
from agent.auth import fetch_agent_token, parse_allow_entry
from agent.exceptions import AgentAuthError


def test_parse_allow_entry_user_write():
    e = parse_allow_entry("user:alice:write")
    assert e.subject_type is SubjectType.USER
    assert e.subject_ref == "alice"
    assert e.role is Role.WRITE


def test_parse_allow_entry_group_read():
    e = parse_allow_entry("group:eng:read")
    assert e.subject_type is SubjectType.GROUP
    assert e.role is Role.READ


def test_parse_allow_entry_group_with_colons():
    # Identity-broker group names contain ':' (app:<service>:<role>); the ref
    # must survive intact so these groups can be granted mount access.
    e = parse_allow_entry("group:app:files:eng:read")
    assert e.subject_type is SubjectType.GROUP
    assert e.subject_ref == "app:files:eng"
    assert e.role is Role.READ


@pytest.mark.parametrize(
    "spec",
    ["bad", "user:alice", "user:alice:write:extra", "user::write", "bogus:a:read", "user:a:admin"],
)
def test_parse_allow_entry_malformed(spec):
    with pytest.raises(ValueError):
        parse_allow_entry(spec)


def _mock_async_client(response):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_fetch_agent_token_success():
    resp = MagicMock(status_code=200)
    resp.json = MagicMock(return_value={"token": "tok123", "user_id": 1})
    with patch("agent.auth.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        token = await fetch_agent_token("https://relay.example.com", "alice", "pw")
    assert token == "tok123"


@pytest.mark.asyncio
async def test_fetch_agent_token_rejected():
    resp = MagicMock(status_code=401)
    with patch("agent.auth.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        with pytest.raises(AgentAuthError):
            await fetch_agent_token("https://relay.example.com", "alice", "bad")


@pytest.mark.asyncio
async def test_fetch_agent_token_missing_token():
    resp = MagicMock(status_code=200)
    resp.json = MagicMock(return_value={})
    with patch("agent.auth.httpx.AsyncClient", return_value=_mock_async_client(resp)):
        with pytest.raises(AgentAuthError):
            await fetch_agent_token("https://relay.example.com", "alice", "pw")
