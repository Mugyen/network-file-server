"""Composition root: wires the server (and, for mount mode, the agent) together.

This is the ONE place server code is allowed to import the agent package —
``build_mount_app`` is the factory the agent calls to turn an assigned mount
into a server ASGI app, and ``run_mount_agent`` hands that factory to the
agent's reconnect loop. Keeping these here (out of the arg-parsing cli.py)
lets composition be exercised without constructing argv, and makes the
agent-import boundary a single, named file.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import uvicorn

from server.app.config import ServerConfig
from server.app.services.auth_service import hash_password
from shared.network import detect_primary_lan_ip
from shared.qr import generate_ascii_qr

if TYPE_CHECKING:
    import argparse

    from agent.connection import MountAppContext


def build_mount_app(ctx: "MountAppContext") -> object:
    """App factory handed to the agent: build the server ASGI app for a mount.

    This is the composition root joining the agent and server packages —
    the agent itself never imports the server. All services (token service,
    share links, ...) are constructed inside create_app and live on
    app.state — no globals are touched, so repeated mounts (reconnects) and
    other in-process apps cannot interfere with each other.
    """
    from server.app.main import create_app as _create_app

    config = ServerConfig(
        shared_folder=ctx.folder,
        port=0,
        password_hash=ctx.password_hash,
        read_only=False,
        receive=False,
        mount_code=ctx.mount_code,
        relay_url=ctx.relay_url,
        identity_secret=ctx.identity_secret,
    )
    return _create_app(config)


def run_mount_agent(args: "argparse.Namespace") -> None:
    """Run the mount agent, handing it the server app factory.

    The agent import is deliberately local and confined to this composition
    root (enforced by tests/test_import_boundaries.py).
    """
    from agent.cli import run_mount

    run_mount(args, build_mount_app)


def run_lan_server(args: "argparse.Namespace") -> None:
    """Validate LAN args, build the server app, print the QR, and serve.

    Exits the process with a message on validation errors (mutually
    exclusive modes, oversized password, bad shared folder).
    """
    if args.read_only and args.receive:
        print("Error: --read-only and --receive cannot be used together")
        sys.exit(1)

    # Validate password length (bcrypt 72-byte limit)
    if args.password is not None and len(args.password.encode("utf-8")) > 72:
        print("Error: Password must not exceed 72 bytes (bcrypt limit)")
        sys.exit(1)

    # Apply defaults for arguments not provided.
    port: int = args.port if args.port is not None else 8000  # FastAPI convention
    host: str = args.host if args.host is not None else "0.0.0.0"  # all interfaces

    folder_path = Path(args.folder).resolve()

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
            identity_secret=None,
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print("\nNetwork File Server Starting...")
    print(f"Sharing folder: {config.shared_folder}")

    if args.password is not None:
        print("  Mode: Password Protected")
    if args.read_only:
        print("  Mode: Read Only")
    if args.receive:
        print("  Mode: Receive Only")

    # Display QR code and server URL for easy device connection.
    try:
        local_ip = detect_primary_lan_ip()
        server_url = f"http://{local_ip}:{port}"
        ascii_qr = generate_ascii_qr(server_url)
        print("\nScan this QR code to connect:\n")
        print(ascii_qr)
        print(f"Server URL: {server_url}")
    except RuntimeError as exc:
        print(f"Warning: Could not detect LAN IP ({exc})")
        print(f"Server will be available at http://localhost:{port}")

    print(f"Local URL: http://localhost:{port}")
    print("Access from any device on the same network!")
    print("\nPress Ctrl+C to stop the server\n")

    # Build the app explicitly — all services live on app.state.
    from server.app.main import create_app

    app = create_app(config)

    try:
        uvicorn.run(app, host=host, port=port)
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as exc:
        print(f"Error starting server: {exc}")
        sys.exit(1)
