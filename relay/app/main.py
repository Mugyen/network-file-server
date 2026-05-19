"""Relay FastAPI application factory.

Creates the relay app with conditional CORS, SecureCookieMiddleware, and
router mounting. CORS is locked down in production (explicit origins with
credentials) and permissive in development (wildcard, no credentials).
"""

import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded

from relay.app.config import get_config, load_config, set_config
from relay.app.logging import RelayEnv
from relay.app.middleware.secure_cookies import SecureCookieMiddleware
from relay.app.rate_limit import limiter, rate_limit_exceeded_handler
from fastapi.staticfiles import StaticFiles

from relay.app.services.mount_registry import set_registry
from relay.app.services.sqlite_registry import SqliteMountRegistry
from relay.app.services.ttl_sweep import run_ttl_sweep


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle — creates SqliteMountRegistry, starts TTL sweep, initializes drop box and file TTL, cleans up on shutdown."""
    import logging
    import os

    from accounts import SqliteAccountStore

    from relay.app.services.account_store import set_account_store
    from relay.app.services.dropbox import init_dropbox, set_dropbox_client
    from relay.app.services.file_ttl_db import FileTtlDb, set_file_ttl_db
    from relay.app.services.file_ttl_sweep import run_file_ttl_sweep
    from relay.app.services.session import RelaySession, set_relay_session
    from server.app.services.connection_manager import manager

    _logger = logging.getLogger("relay.lifespan")

    config = get_config()
    registry = await SqliteMountRegistry.create(config.db_path)
    set_registry(registry)

    # Accounts registry + session signer (shared across all mounts).
    account_store = await SqliteAccountStore.create(config.accounts_db_path)
    set_account_store(account_store)
    set_relay_session(RelaySession(config.session_secret))

    # Initialize file TTL tracking on the same SQLite connection
    file_ttl_db = FileTtlDb(registry._db)
    await file_ttl_db.init_table()
    set_file_ttl_db(file_ttl_db)

    # Initialize drop box server app and register as a first-class mount
    dropbox_client = await init_dropbox(Path(config.data_dir), config.dropbox_code)
    set_dropbox_client(dropbox_client)
    await registry.register(
        code=config.dropbox_code,
        connection=None,
        agent_ip="127.0.0.1",
        created_at=time.time(),
        expires_at=None,
    )

    # Boot-time cleanup: delete expired drop box files
    expired_paths = await file_ttl_db.delete_expired_for_mount(config.dropbox_code)
    for fp in expired_paths:
        full_path = Path(config.data_dir) / "dropbox" / fp.lstrip("/")
        if full_path.exists():
            os.remove(full_path)
            _logger.info("Boot cleanup: deleted expired drop box file %s", fp)

    sweep_task = asyncio.create_task(
        run_ttl_sweep(registry, config)
    )
    file_ttl_sweep_task = asyncio.create_task(
        run_file_ttl_sweep(file_ttl_db, Path(config.data_dir), config.dropbox_code, 60, manager.broadcast_all)
    )
    yield
    sweep_task.cancel()
    file_ttl_sweep_task.cancel()
    try:
        await sweep_task
    except asyncio.CancelledError:
        pass
    try:
        await file_ttl_sweep_task
    except asyncio.CancelledError:
        pass
    await dropbox_client.aclose()
    set_dropbox_client(None)
    set_file_ttl_db(None)
    await account_store.close()
    set_account_store(None)
    set_relay_session(None)
    await registry.close()


def create_relay_app(config_path: Path | None = None) -> FastAPI:
    """Create and configure the relay FastAPI application.

    Loads config from YAML + env vars, sets up CORS based on environment,
    adds SecureCookieMiddleware, includes all routers, and initializes
    the mount registry. Starts a background TTL sweep task via lifespan.

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

    application = FastAPI(title="Network File Server Relay", lifespan=lifespan)

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

    # SlowAPI rate limiter — attach to app state and register 429 handler.
    # Placed after middleware setup but before router inclusion.
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Mount static files for OG image and future assets
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from relay.app.routers.admin import router as admin_router
    from relay.app.routers.agent_ws import router as agent_ws_router
    from relay.app.routers.auth import router as auth_router
    from relay.app.routers.health import router as health_router
    from relay.app.routers.landing import router as landing_router
    from relay.app.routers.access_requests import router as access_requests_router
    from relay.app.routers.mount_proxy import router as mount_proxy_router
    from relay.app.routers.pages import router as pages_router
    from relay.app.routers.user_storage import router as user_storage_router

    # Serve the client bundle's assets at the relay root for account pages.
    client_assets = Path(__file__).resolve().parent.parent.parent / "client" / "dist" / "assets"
    if client_assets.exists() and client_assets.is_dir():
        application.mount(
            "/assets",
            StaticFiles(directory=str(client_assets)),
            name="client-assets",
        )

    application.include_router(health_router)
    application.include_router(landing_router)
    application.include_router(pages_router)
    application.include_router(auth_router)
    application.include_router(admin_router)
    application.include_router(access_requests_router)
    application.include_router(user_storage_router)
    application.include_router(agent_ws_router)
    application.include_router(mount_proxy_router)

    return application


app = create_relay_app()
