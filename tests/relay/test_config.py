"""Tests for relay config module — YAML loading, env var overrides, validation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from relay.app.config import RelayConfig, load_config
from relay.app.logging import RelayEnv


# Path to the actual config.yaml in the relay package
_CONFIG_YAML = Path(__file__).resolve().parent.parent.parent / "relay" / "config.yaml"


# ---------------------------------------------------------------------------
# load_config with default config.yaml
# ---------------------------------------------------------------------------


def test_load_config_returns_relay_config_with_defaults() -> None:
    config = load_config(_CONFIG_YAML)
    assert isinstance(config, RelayConfig)
    assert config.env == RelayEnv.DEVELOPMENT
    assert config.mount_reg_rate == "5/hour"
    assert config.proxy_request_rate == "300/minute"
    assert config.max_ttl_seconds == 86400
    assert config.max_mounts_per_ip == 5
    assert config.ttl_sweep_interval_seconds == 45
    assert config.warning_before_seconds == 300


# ---------------------------------------------------------------------------
# Env var overrides
# ---------------------------------------------------------------------------


def test_load_config_relay_env_override() -> None:
    with patch.dict(os.environ, {"RELAY_ENV": "production", "RELAY_ALLOWED_ORIGINS": "https://example.com"}):
        config = load_config(_CONFIG_YAML)
    assert config.env == RelayEnv.PRODUCTION


def test_load_config_allowed_origins_override() -> None:
    with patch.dict(os.environ, {"RELAY_ALLOWED_ORIGINS": "https://a.com, https://b.com"}):
        config = load_config(_CONFIG_YAML)
    assert config.allowed_origins == ["https://a.com", "https://b.com"]


def test_load_config_max_ttl_seconds_override() -> None:
    with patch.dict(os.environ, {"RELAY_MAX_TTL_SECONDS": "3600"}):
        config = load_config(_CONFIG_YAML)
    assert config.max_ttl_seconds == 3600


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_load_config_production_requires_allowed_origins() -> None:
    with patch.dict(os.environ, {"RELAY_ENV": "production"}, clear=False):
        # Remove RELAY_ALLOWED_ORIGINS if present
        env = {k: v for k, v in os.environ.items() if k != "RELAY_ALLOWED_ORIGINS"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="RELAY_ALLOWED_ORIGINS"):
                load_config(_CONFIG_YAML)


# ---------------------------------------------------------------------------
# data_dir and dropbox_code fields
# ---------------------------------------------------------------------------


def test_load_config_data_dir_default() -> None:
    config = load_config(_CONFIG_YAML)
    assert config.data_dir == "/tmp/relay-data"


def test_load_config_dropbox_code_default() -> None:
    config = load_config(_CONFIG_YAML)
    assert config.dropbox_code == "dropbox"


def test_load_config_data_dir_env_override() -> None:
    with patch.dict(os.environ, {"RELAY_DATA_DIR": "/custom/data"}):
        config = load_config(_CONFIG_YAML)
    assert config.data_dir == "/custom/data"


def test_load_config_dropbox_code_env_override() -> None:
    with patch.dict(os.environ, {"RELAY_DROPBOX_CODE": "public-box"}):
        config = load_config(_CONFIG_YAML)
    assert config.dropbox_code == "public-box"
