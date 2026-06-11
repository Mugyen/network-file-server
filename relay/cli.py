"""CLI entry point for the relay server."""
import argparse
import os

import uvicorn

from relay.app.logging import RelayEnv, configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Network File Server relay")
    parser.add_argument("--host", type=str, help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Port number (default: PORT env var or 8001)")
    args = parser.parse_args()

    # Explicit None checks — argparse returns None when flags are omitted
    host: str = args.host if args.host is not None else "0.0.0.0"

    # PORT env var is the Cloud Run convention; --port flag overrides it
    port_default: int = int(os.environ.get("PORT", "8001"))
    port: int = args.port if args.port is not None else port_default

    # RELAY_ENV controls logging format (JSON in production, text in development)
    relay_env_str: str = os.environ.get("RELAY_ENV", "development")
    env = RelayEnv(relay_env_str)
    configure_logging(env)

    uvicorn.run(
        "relay.app.main:create_relay_app",
        factory=True,
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
