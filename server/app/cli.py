"""CLI entry point for the WiFi File Server.

Provides main() for argparse-based CLI and run_with_defaults() convenience function.
Supports two modes:
  - LAN mode (default): wifi-file-server <folder> [options]
  - Mount mode: wifi-file-server mount <folder> --server <url>

Subcommand detection: _parse_args() inspects argv[0] for known subcommands.
When 'mount' is detected, the mount parser is used directly. Otherwise, the LAN
parser handles the invocation. This avoids argparse's positional-vs-subparser
conflict where nargs='?' would greedily consume 'mount' as the folder argument.
"""

import argparse
import secrets
import sys
from typing import Optional

import uvicorn

from agent.duration import parse_duration
from server.app.config import ServerConfig, set_server_config
from server.app.services.auth_service import (
    AuthTokenService,
    hash_password,
    set_token_service,
)
from server.app.services.share_service import ShareLinkService, set_share_service
from server.app.services.network_service import detect_primary_lan_ip
from server.app.services.qr_service import generate_ascii_qr

# Known subcommand names — used to detect mode in _parse_args and main()
_SUBCOMMANDS: frozenset = frozenset({"mount"})


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the LAN-mode argument parser.

    This parser handles the default invocation:
      wifi-file-server <folder> [--port PORT] [--host HOST] [--password PW]
                                [--read-only] [--receive]

    It does NOT include mount subcommand parsing. Mount is handled separately
    by _build_mount_parser() and _parse_args() which routes based on argv.

    Backward compatibility: existing server tests call _build_parser() directly
    and expect LAN-mode arg parsing. Those tests continue to work unchanged.
    """
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
    parser.add_argument(
        "--password",
        type=str,
        help="Password to protect the server (max 72 bytes)",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Start server in read-only mode (no uploads/deletes)",
    )
    parser.add_argument(
        "--receive",
        action="store_true",
        help="Start server in receive-only mode (uploads only, no downloads)",
    )
    return parser


def _build_mount_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the mount subcommand.

    Handles: wifi-file-server mount <folder> --server <url> [--name NAME]
    """
    parser = argparse.ArgumentParser(
        description="Mount a local folder through a relay server",
    )
    parser.add_argument(
        "folder",
        help="Path to the local folder to share via relay",
    )
    parser.add_argument(
        "--server",
        required=True,
        help="Relay server base URL (e.g. https://relay.example.com)",
    )
    parser.add_argument(
        "--name",
        help="Optional display name for the mount (defaults to folder basename)",
    )
    parser.add_argument(
        "--password",
        type=str,
        help="Password to protect the remote mount (max 72 bytes)",
    )
    parser.add_argument(
        "--ttl",
        type=parse_duration,
        dest="ttl_seconds",
        help="Auto-expire duration (e.g. 30m, 2h, 1d). Agent exits cleanly after this time.",
    )
    return parser


def _parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    """Parse CLI arguments, routing to the correct parser based on subcommand.

    When argv[0] is 'mount', routes to _build_mount_parser() and wraps the
    result in a Namespace with command='mount'. Otherwise routes to the LAN
    parser (_build_parser()) with command=None.

    Args:
        argv: Argument list (excluding program name); defaults to sys.argv[1:].

    Returns:
        Parsed argparse.Namespace with a 'command' attribute ('mount' or None).

    Raises:
        SystemExit: On argument parse errors (delegated to argparse).
    """
    args_list = sys.argv[1:] if argv is None else list(argv)

    if args_list and args_list[0] in _SUBCOMMANDS:
        subcommand = args_list[0]
        mount_args = _build_mount_parser().parse_args(args_list[1:])
        return argparse.Namespace(
            command=subcommand,
            folder=mount_args.folder,
            server=mount_args.server,
            name=mount_args.name,
            password=mount_args.password,
            ttl_seconds=mount_args.ttl_seconds,
        )

    # LAN mode: parse with standard parser, add command=None
    lan_args = _build_parser().parse_args(args_list)
    return argparse.Namespace(
        command=None,
        folder=lan_args.folder,
        port=lan_args.port,
        host=lan_args.host,
        password=lan_args.password,
        read_only=lan_args.read_only,
        receive=lan_args.receive,
    )


def main() -> None:
    """Parse CLI arguments and start the server or mount agent.

    Dispatches based on args.command:
    - 'mount': imports and calls agent.cli.run_mount(args)
    - None (bare invocation): requires folder, validates it, starts LAN server
    """
    args = _parse_args()

    if args.command == "mount":
        from agent.cli import run_mount
        run_mount(args)
        return

    # LAN mode validation
    if args.read_only and args.receive:
        print("Error: --read-only and --receive cannot be used together")
        sys.exit(1)

    # Validate password length (bcrypt 72-byte limit)
    if args.password is not None and len(args.password.encode("utf-8")) > 72:
        print("Error: Password must not exceed 72 bytes (bcrypt limit)")
        sys.exit(1)

    # Apply defaults for arguments not provided
    # Default port 8000 for FastAPI convention
    port: int = args.port if args.port is not None else 8000
    # Default 0.0.0.0 for LAN access
    host: str = args.host if args.host is not None else "0.0.0.0"

    from pathlib import Path

    folder_path = Path(args.folder).resolve()

    # Hash password if provided
    password_hash: bytes | None = None
    if args.password is not None:
        password_hash = hash_password(args.password)

    try:
        config = ServerConfig(
            shared_folder=folder_path,
            port=port,
            password_hash=password_hash,
            read_only=args.read_only,
            receive=args.receive,
            mount_code=None,
            relay_url=None,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    set_server_config(config)

    # Create and register AuthTokenService when password protection is enabled
    # Generate a secret key for share links (always needed regardless of password)
    share_secret_key = secrets.token_hex(32)
    if args.password is not None:
        # 32-byte hex secret (64 hex chars) for signing session tokens
        secret_key = secrets.token_hex(32)
        set_token_service(AuthTokenService(secret_key))

    # Initialize ShareLinkService for share link functionality
    set_share_service(ShareLinkService(share_secret_key))

    print(f"\nWiFi File Server Starting...")
    print(f"Sharing folder: {config.shared_folder}")

    # Print active modes
    if args.password is not None:
        print("  Mode: Password Protected")
    if args.read_only:
        print("  Mode: Read Only")
    if args.receive:
        print("  Mode: Receive Only")

    # Display QR code and server URL for easy device connection
    try:
        local_ip = detect_primary_lan_ip()
        server_url = f"http://{local_ip}:{port}"
        ascii_qr = generate_ascii_qr(server_url)
        print(f"\nScan this QR code to connect:\n")
        print(ascii_qr)
        print(f"Server URL: {server_url}")
    except RuntimeError as exc:
        print(f"Warning: Could not detect LAN IP ({exc})")
        print(f"Server will be available at http://localhost:{port}")

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
