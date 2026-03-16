"""Relay FastAPI application factory.

Creates the relay app with CORS middleware and router mounting.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relay.app.services.mount_registry import MountRegistry, set_registry


def create_relay_app() -> FastAPI:
    """Create and configure the relay FastAPI application.

    - Adds CORSMiddleware with wildcard origins.
    - Includes the landing page, agent WebSocket, and mount proxy routers.
    - Initializes a fresh MountRegistry.
    """
    application = FastAPI(title="Network File Server Relay")

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
