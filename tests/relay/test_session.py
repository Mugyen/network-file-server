"""Tests for the relay session signer and accounts config fields."""

import logging
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from relay.app.config import load_config
from relay.app.exceptions import InvalidSessionError
from relay.app.services.account_store import get_account_store, set_account_store
from relay.app.services.session import (
    AGENT_TOKEN_MAX_AGE_SECONDS,
    SESSION_MAX_AGE_SECONDS,
    RelaySession,
    get_relay_session,
    set_relay_session,
)

_CONFIG_YAML = Path(__file__).resolve().parent.parent.parent / "relay" / "config.yaml"


# ---------------------------------------------------------------------------
# RelaySession — browser session tokens
# ---------------------------------------------------------------------------


def test_session_roundtrip() -> None:
    s = RelaySession("secret-key")
    token = s.issue(42, "alice")
    identity = s.verify(token, SESSION_MAX_AGE_SECONDS)
    assert identity.user_id == 42
    assert identity.username == "alice"


def test_verify_session_cookie_helper() -> None:
    s = RelaySession("secret-key")
    identity = s.verify_session_cookie(s.issue(7, "bob"))
    assert identity.user_id == 7


def test_empty_token_rejected() -> None:
    s = RelaySession("secret-key")
    with pytest.raises(InvalidSessionError):
        s.verify("", SESSION_MAX_AGE_SECONDS)


def test_tampered_token_rejected() -> None:
    s = RelaySession("secret-key")
    other = RelaySession("different-key")
    token = other.issue(1, "mallory")
    with pytest.raises(InvalidSessionError):
        s.verify(token, SESSION_MAX_AGE_SECONDS)


def test_expired_token_rejected() -> None:
    s = RelaySession("secret-key")
    token = s.issue(1, "alice")
    time.sleep(1.05)
    with pytest.raises(InvalidSessionError):
        s.verify(token, 0)


def test_constructor_rejects_empty_secret() -> None:
    with pytest.raises(ValueError):
        RelaySession("")


# ---------------------------------------------------------------------------
# Agent-owner tokens — distinct salt, purpose-checked
# ---------------------------------------------------------------------------


def test_agent_owner_token_roundtrip() -> None:
    s = RelaySession("secret-key")
    token = s.issue_agent_owner_token(99)
    assert s.verify_agent_owner_token(token) == 99


def test_session_token_not_valid_as_agent_token() -> None:
    s = RelaySession("secret-key")
    session_token = s.issue(99, "alice")
    with pytest.raises(InvalidSessionError):
        s.verify_agent_owner_token(session_token)


def test_agent_token_max_age_is_short() -> None:
    assert AGENT_TOKEN_MAX_AGE_SECONDS <= 300


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------


def test_session_singleton_raises_before_set() -> None:
    set_relay_session(None)
    with pytest.raises(RuntimeError, match="RelaySession has not been set"):
        get_relay_session()
    s = RelaySession("k")
    set_relay_session(s)
    assert get_relay_session() is s
    set_relay_session(None)


def test_account_store_singleton_raises_before_set() -> None:
    set_account_store(None)
    with pytest.raises(RuntimeError, match="AccountStore has not been set"):
        get_account_store()


# ---------------------------------------------------------------------------
# Config: new accounts fields
# ---------------------------------------------------------------------------


def test_config_defaults_from_yaml() -> None:
    config = load_config(_CONFIG_YAML)
    assert config.session_secret == "dev-insecure-relay-session-secret"
    assert config.admin_users == []
    assert config.default_user_quota_bytes == 1073741824
    # Empty yaml value -> sibling of db_path.
    assert config.accounts_db_path.endswith("accounts.db")


def test_config_admin_users_env_lowercased() -> None:
    with patch.dict(os.environ, {"RELAY_ADMIN_USERS": "Alice, BOB ,carol"}):
        config = load_config(_CONFIG_YAML)
    assert config.admin_users == ["alice", "bob", "carol"]


def test_config_accounts_db_sibling_of_db_path() -> None:
    with patch.dict(os.environ, {"RELAY_DB_PATH": "/var/lib/relay/mounts.db"}):
        config = load_config(_CONFIG_YAML)
    assert config.accounts_db_path == "/var/lib/relay/accounts.db"


def test_config_memory_db_path_yields_memory_accounts() -> None:
    with patch.dict(os.environ, {"RELAY_DB_PATH": ":memory:"}):
        config = load_config(_CONFIG_YAML)
    assert config.accounts_db_path == ":memory:"


def test_config_default_quota_env_override() -> None:
    with patch.dict(os.environ, {"RELAY_DEFAULT_USER_QUOTA_BYTES": "500"}):
        config = load_config(_CONFIG_YAML)
    assert config.default_user_quota_bytes == 500


def test_missing_session_secret_generates_ephemeral_and_warns(
    tmp_path: Path, caplog
) -> None:
    minimal = tmp_path / "config.yaml"
    minimal.write_text(
        "env: development\n"
        "allowed_origins: []\n"
        "db_path: /tmp/mounts.db\n"
    )
    clean_env = {
        k: v for k, v in os.environ.items() if k != "RELAY_SESSION_SECRET"
    }
    with patch.dict(os.environ, clean_env, clear=True):
        with caplog.at_level(logging.WARNING):
            config = load_config(minimal)
    assert len(config.session_secret) > 0
    assert "RELAY_SESSION_SECRET not set" in caplog.text
