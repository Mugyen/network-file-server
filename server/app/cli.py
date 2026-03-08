"""CLI entry point for the WiFi File Server.

Provides main() for argparse-based CLI and run_with_defaults() convenience function.
"""

import argparse
import sys

import uvicorn

from server.app.config import ServerConfig, set_server_config


def _get_local_ip() -> str:
    """Detect the local IP address for LAN access.

    Connects to a remote DNS server to determine the local IP.
    Falls back to 127.0.0.1 if detection fails.
    """
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="WiFi File Server - Share files over local network"
    )
    parser.add_argument(
        "folder",
        help="Path to the folder to share",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        help="Port to run the server on",
    )
    parser.add_argument(
        "--host",
        type=str,
        help="Host to bind to",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and start the server.

    Uses argparse for: folder (positional, required), --port/-p (int), --host (str).
    Validates folder via ServerConfig. Starts uvicorn programmatically.
    """
    parser = _build_parser()
    args = parser.parse_args()

    # Apply defaults for arguments not provided
    # Default port 8000 for FastAPI convention
    port: int = args.port if args.port is not None else 8000
    # Default 0.0.0.0 for LAN access
    host: str = args.host if args.host is not None else "0.0.0.0"

    from pathlib import Path

    folder_path = Path(args.folder).resolve()

    try:
        config = ServerConfig(shared_folder=folder_path, port=port)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    set_server_config(config)

    local_ip = _get_local_ip()

    print(f"\nWiFi File Server Starting...")
    print(f"Sharing folder: {config.shared_folder}")
    print(f"Server URL: http://{local_ip}:{port}")
    print(f"Local URL: http://localhost:{port}")
    print(f"Access from any device on the same network!")
    print(f"\nPress Ctrl+C to stop the server\n")

    try:
        uvicorn.run("server.app.main:app", host=host, port=port)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as exc:
        print(f"Error starting server: {exc}")
        sys.exit(1)


def run_with_defaults(folder: str) -> None:
    """Start the server with default port 8000 and host 0.0.0.0.

    Convenience function for programmatic use.
    Port 8000: FastAPI convention.
    Host 0.0.0.0: Binds to all interfaces for LAN access.
    """
    sys.argv = ["wifi-file-server", folder]
    main()


if __name__ == "__main__":
    main()
