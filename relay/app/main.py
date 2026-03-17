"""Relay FastAPI application factory.

Creates the relay app with conditional CORS, SecureCookieMiddleware, and
router mounting. CORS is locked down in production (explicit origins with
credentials) and permissive in development (wildcard, no credentials).
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relay.app.config import load_config, set_config
from relay.app.logging import RelayEnv
from relay.app.middleware.secure_cookies import SecureCookieMiddleware
from relay.app.services.mount_registry import MountRegistry, set_registry


def create_relay_app(config_path: Path | None = None) -> FastAPI:
    """Create and configure the relay FastAPI application.

    Loads config from YAML + env vars, sets up CORS based on environment,
    adds SecureCookieMiddleware, includes all routers, and initializes
    the mount registry.

    Args:
        config_path: Path to config.yaml. If None, uses the default
            relay/config.yaml adjacent to the relay package.

    Raises:
        ValueError: If RELAY_ENV=production and RELAY_ALLOWED_ORIGINS is not set.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"

    config = load_config(config_path)
    set_config(config)

    application = FastAPI(title="Network File Server Relay")

    # SecureCookieMiddleware added first -- becomes inner middleware.
    # It stamps Secure on Set-Cookie headers when behind HTTPS proxy.
    application.add_middleware(SecureCookieMiddleware)

    # CORSMiddleware added second -- becomes outer middleware (Starlette LIFO).
    # Handles preflight before anything else.
    if config.env == RelayEnv.PRODUCTION:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=config.allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    from relay.app.routers.agent_ws import router as agent_ws_router
    from relay.app.routers.health import router as health_router
    from relay.app.routers.landing import router as landing_router
    from relay.app.routers.mount_proxy import router as mount_proxy_router

    application.include_router(health_router)
    application.include_router(landing_router)
    application.include_router(agent_ws_router)
    application.include_router(mount_proxy_router)

    set_registry(MountRegistry())

    return application


app = create_relay_app()
