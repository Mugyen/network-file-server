"""Relay FastAPI application factory.

Creates the relay app with conditional CORS, SecureCookieMiddleware, and
router mounting. CORS is locked down in production (explicit origins with
credentials) and permissive in development (wildcard, no credentials).
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relay.app.logging import RelayEnv
from relay.app.middleware.secure_cookies import SecureCookieMiddleware
from relay.app.services.mount_registry import MountRegistry, set_registry


def create_relay_app() -> FastAPI:
    """Create and configure the relay FastAPI application.

    - Reads RELAY_ENV to determine CORS policy.
    - Adds SecureCookieMiddleware (inner) then CORSMiddleware (outer).
    - Includes the landing page, agent WebSocket, mount proxy, and health routers.
    - Initializes a fresh MountRegistry.

    Raises:
        ValueError: If RELAY_ENV=production and RELAY_ALLOWED_ORIGINS is not set.
    """
    relay_env_str: str = os.environ.get("RELAY_ENV", "development")
    env = RelayEnv(relay_env_str)

    application = FastAPI(title="Network File Server Relay")

    # SecureCookieMiddleware added first -- becomes inner middleware.
    # It stamps Secure on Set-Cookie headers when behind HTTPS proxy.
    application.add_middleware(SecureCookieMiddleware)

    # CORSMiddleware added second -- becomes outer middleware (Starlette LIFO).
    # Handles preflight before anything else.
    if env == RelayEnv.PRODUCTION:
        raw_origins: str = os.environ.get("RELAY_ALLOWED_ORIGINS", "")
        if not raw_origins.strip():
            raise ValueError(
                "RELAY_ALLOWED_ORIGINS must be set when RELAY_ENV=production. "
                "Provide a comma-separated list of allowed origins."
            )
        origins: list[str] = [o.strip() for o in raw_origins.split(",")]
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
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

    from relay.app.routers.health import router as health_router
    from relay.app.routers.landing import router as landing_router
    from relay.app.routers.agent_ws import router as agent_ws_router
    from relay.app.routers.mount_proxy import router as mount_proxy_router

    application.include_router(health_router)
    application.include_router(landing_router)
    application.include_router(agent_ws_router)
    application.include_router(mount_proxy_router)

    set_registry(MountRegistry())

    return application


app = create_relay_app()
