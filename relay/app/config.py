"""Relay configuration module — loads config.yaml with env var overrides.

Centralizes all relay configuration into a single dataclass. YAML provides
development defaults; environment variables override individual fields for
Cloud Run deployments (12-factor app style).
"""

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import yaml

from relay.app.logging import RelayEnv

logger = logging.getLogger(__name__)


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
    db_path: str
    data_dir: str
    dropbox_code: str
    session_secret: str
    admin_users: list[str]
    accounts_db_path: str
    default_user_quota_bytes: int
    auth_signup_rate: str
    auth_login_rate: str
    auth_agent_token_rate: str
    # Public base URL the relay names itself by (drop box QR etc.).
    # None = no public identity known (dev fallback to local IP).
    public_url: str | None = None


def load_config(config_path: Path) -> RelayConfig:
    """Load relay config from a YAML file with env var overrides.

    Each field can be overridden by a corresponding env var:
      - RELAY_ENV -> env
      - RELAY_ALLOWED_ORIGINS -> allowed_origins (comma-separated)
      - RELAY_PUBLIC_URL -> public_url (defaults to the first allowed origin)
      - RELAY_MOUNT_REG_RATE -> mount_reg_rate
      - RELAY_PROXY_REQUEST_RATE -> proxy_request_rate
      - RELAY_MAX_TTL_SECONDS -> max_ttl_seconds
      - RELAY_MAX_MOUNTS_PER_IP -> max_mounts_per_ip
      - RELAY_TTL_SWEEP_INTERVAL -> ttl_sweep_interval_seconds
      - RELAY_WARNING_BEFORE_SECONDS -> warning_before_seconds
      - RELAY_SESSION_SECRET -> session_secret (ephemeral if unset)
      - RELAY_ADMIN_USERS -> admin_users (comma-separated, lowercased)
      - RELAY_ACCOUNTS_DB_PATH -> accounts_db_path
      - RELAY_DEFAULT_USER_QUOTA_BYTES -> default_user_quota_bytes

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

    # Public base URL the relay is reached at (scheme + host), used wherever
    # the relay must name itself (e.g. the drop box QR code). Explicit env/yaml
    # value wins; otherwise the first allowed origin is the canonical one.
    public_url_raw: str = os.environ.get(
        "RELAY_PUBLIC_URL",
        raw.get("public_url") or "",
    ).strip()
    if not public_url_raw and allowed_origins:
        public_url_raw = allowed_origins[0]
    public_url: str | None = public_url_raw.rstrip("/") or None

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
    db_path: str = os.environ.get(
        "RELAY_DB_PATH",
        raw.get("db_path", "/tmp/mounts.db"),
    )
    data_dir: str = os.environ.get(
        "RELAY_DATA_DIR",
        raw.get("data_dir", "/data/"),
    )
    dropbox_code: str = os.environ.get(
        "RELAY_DROPBOX_CODE",
        raw.get("dropbox_code", "dropbox"),
    )

    # --- Accounts (v1.3) ---------------------------------------------------
    session_secret: str = os.environ.get(
        "RELAY_SESSION_SECRET",
        raw.get("session_secret") or "",
    )
    if not session_secret:
        session_secret = secrets.token_urlsafe(32)
        logger.warning(
            "RELAY_SESSION_SECRET not set -- generated an ephemeral secret. "
            "All sessions will be invalidated on relay restart. Set "
            "RELAY_SESSION_SECRET for stable sessions in production."
        )

    admin_env: str | None = os.environ.get("RELAY_ADMIN_USERS")
    if admin_env is not None:
        admin_users: list[str] = [
            u.strip().lower() for u in admin_env.split(",") if u.strip()
        ]
    else:
        admin_users = [
            str(u).strip().lower()
            for u in raw.get("admin_users", [])
            if str(u).strip()
        ]

    if db_path == ":memory:":
        default_accounts_db = ":memory:"
    else:
        default_accounts_db = str(Path(db_path).parent / "accounts.db")
    accounts_db_path: str = os.environ.get(
        "RELAY_ACCOUNTS_DB_PATH",
        raw.get("accounts_db_path") or default_accounts_db,
    )

    default_user_quota_bytes: int = int(os.environ.get(
        "RELAY_DEFAULT_USER_QUOTA_BYTES",
        str(raw.get("default_user_quota_bytes", 1073741824)),
    ))

    auth_signup_rate: str = os.environ.get(
        "RELAY_AUTH_SIGNUP_RATE",
        rate_limits.get("auth_signup", "5/hour"),
    )
    auth_login_rate: str = os.environ.get(
        "RELAY_AUTH_LOGIN_RATE",
        rate_limits.get("auth_login", "10/minute"),
    )
    auth_agent_token_rate: str = os.environ.get(
        "RELAY_AUTH_AGENT_TOKEN_RATE",
        rate_limits.get("auth_agent_token", "10/minute"),
    )

    # Validate: production requires explicit allowed_origins
    if env == RelayEnv.PRODUCTION and not allowed_origins:
        raise ValueError(
            "RELAY_ALLOWED_ORIGINS must be set when RELAY_ENV=production. "
            "Provide a comma-separated list of allowed origins."
        )

    return RelayConfig(
        env=env,
        allowed_origins=allowed_origins,
        public_url=public_url,
        mount_reg_rate=mount_reg_rate,
        proxy_request_rate=proxy_request_rate,
        max_ttl_seconds=max_ttl_seconds,
        max_mounts_per_ip=max_mounts_per_ip,
        ttl_sweep_interval_seconds=ttl_sweep_interval_seconds,
        warning_before_seconds=warning_before_seconds,
        db_path=db_path,
        data_dir=data_dir,
        dropbox_code=dropbox_code,
        session_secret=session_secret,
        admin_users=admin_users,
        accounts_db_path=accounts_db_path,
        default_user_quota_bytes=default_user_quota_bytes,
        auth_signup_rate=auth_signup_rate,
        auth_login_rate=auth_login_rate,
        auth_agent_token_rate=auth_agent_token_rate,
    )
