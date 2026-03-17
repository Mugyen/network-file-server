"""Relay configuration module — loads config.yaml with env var overrides.

Centralizes all relay configuration into a single dataclass. YAML provides
development defaults; environment variables override individual fields for
Cloud Run deployments (12-factor app style).
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from relay.app.logging import RelayEnv


@dataclass(frozen=True)
class RelayConfig:
    """Immutable relay configuration loaded from YAML + env var overrides."""

    env: RelayEnv
    allowed_origins: list[str]
    mount_reg_rate: str
    proxy_request_rate: str
    max_ttl_seconds: int
    max_mounts_per_ip: int
    ttl_sweep_interval_seconds: int
    warning_before_seconds: int


def load_config(config_path: Path) -> RelayConfig:
    """Load relay config from a YAML file with env var overrides.

    Each field can be overridden by a corresponding env var:
      - RELAY_ENV -> env
      - RELAY_ALLOWED_ORIGINS -> allowed_origins (comma-separated)
      - RELAY_MOUNT_REG_RATE -> mount_reg_rate
      - RELAY_PROXY_REQUEST_RATE -> proxy_request_rate
      - RELAY_MAX_TTL_SECONDS -> max_ttl_seconds
      - RELAY_MAX_MOUNTS_PER_IP -> max_mounts_per_ip
      - RELAY_TTL_SWEEP_INTERVAL -> ttl_sweep_interval_seconds
      - RELAY_WARNING_BEFORE_SECONDS -> warning_before_seconds

    Args:
        config_path: Absolute or relative path to the config YAML file.

    Returns:
        A frozen RelayConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If env is PRODUCTION and allowed_origins is empty.
    """
    with open(config_path) as f:
        raw: dict = yaml.safe_load(f)

    rate_limits: dict = raw.get("rate_limits", {})
    ttl: dict = raw.get("ttl", {})

    # Load from YAML first, then override with env vars
    env_str: str = os.environ.get("RELAY_ENV", raw.get("env", "development"))
    env = RelayEnv(env_str)

    origins_env: str | None = os.environ.get("RELAY_ALLOWED_ORIGINS")
    if origins_env is not None:
        allowed_origins: list[str] = [o.strip() for o in origins_env.split(",") if o.strip()]
    else:
        allowed_origins = raw.get("allowed_origins", [])

    mount_reg_rate: str = os.environ.get(
        "RELAY_MOUNT_REG_RATE",
        rate_limits.get("mount_registration", "5/hour"),
    )
    proxy_request_rate: str = os.environ.get(
        "RELAY_PROXY_REQUEST_RATE",
        rate_limits.get("proxy_requests", "300/minute"),
    )
    max_ttl_seconds: int = int(os.environ.get(
        "RELAY_MAX_TTL_SECONDS",
        str(ttl.get("max_seconds", 86400)),
    ))
    max_mounts_per_ip: int = int(os.environ.get(
        "RELAY_MAX_MOUNTS_PER_IP",
        str(rate_limits.get("max_mounts_per_ip", 5)),
    ))
    ttl_sweep_interval_seconds: int = int(os.environ.get(
        "RELAY_TTL_SWEEP_INTERVAL",
        str(ttl.get("sweep_interval_seconds", 45)),
    ))
    warning_before_seconds: int = int(os.environ.get(
        "RELAY_WARNING_BEFORE_SECONDS",
        str(ttl.get("warning_before_seconds", 300)),
    ))

    # Validate: production requires explicit allowed_origins
    if env == RelayEnv.PRODUCTION and not allowed_origins:
        raise ValueError(
            "RELAY_ALLOWED_ORIGINS must be set when RELAY_ENV=production. "
            "Provide a comma-separated list of allowed origins."
        )

    return RelayConfig(
        env=env,
        allowed_origins=allowed_origins,
        mount_reg_rate=mount_reg_rate,
        proxy_request_rate=proxy_request_rate,
        max_ttl_seconds=max_ttl_seconds,
        max_mounts_per_ip=max_mounts_per_ip,
        ttl_sweep_interval_seconds=ttl_sweep_interval_seconds,
        warning_before_seconds=warning_before_seconds,
    )


_config: RelayConfig | None = None


def get_config() -> RelayConfig:
    """Return the global RelayConfig singleton.

    Raises:
        RuntimeError: If set_config() has not been called.
    """
    if _config is None:
        raise RuntimeError("RelayConfig has not been initialized. Call set_config() first.")
    return _config


def set_config(config: RelayConfig) -> None:
    """Install the global RelayConfig singleton.

    Called by the app factory during startup and by tests to inject config.
    """
    global _config
    _config = config
