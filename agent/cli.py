"""Agent CLI entry point — mount subcommand for remote relay sharing.

Provides run_mount() which is called from server/app/cli.py when the user
invokes `wifi-file-server mount <folder> --server <url>`.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from agent.connection import run_agent_loop
from server.app.services.auth_service import hash_password

# Alias for patching in tests
asyncio_run = asyncio.run


def run_mount(args: argparse.Namespace) -> None:
    """Execute the mount subcommand — connect to relay and serve local folder.

    Resolves folder path, validates it exists and is a directory, optionally
    hashes the password, then starts the agent connection loop via asyncio.run().
    Handles Ctrl+C gracefully by printing "Unmounting..." and exiting cleanly.

    Args:
        args: Parsed argparse.Namespace with attributes:
              - folder (str): Path to the local directory to share.
              - server (str): Relay server base URL.
              - name (str | None): Optional display name; defaults to folder basename.
              - password (str | None): Optional password to protect the mount.
              - ttl_seconds (int | None): Optional TTL in seconds for auto-expiry.

    Raises:
        SystemExit(1): If folder does not exist, is not a directory, or password
                       exceeds 72 bytes.
    """
    folder = Path(args.folder).resolve()

    if not folder.exists():
        print(f"Error: Folder '{folder}' does not exist")
        sys.exit(1)

    if not folder.is_dir():
        print(f"Error: '{folder}' is not a directory")
        sys.exit(1)

    # Validate and hash password if provided (bcrypt 72-byte limit)
    password_hash: bytes | None = None
    if args.password is not None:
        if len(args.password.encode("utf-8")) > 72:
            print("Error: Password must not exceed 72 bytes (bcrypt limit)")
            sys.exit(1)
        password_hash = hash_password(args.password)

    ttl_seconds: int | None = args.ttl_seconds

    name: str = args.name if args.name is not None else folder.name
    server_url: str = args.server

    print(f"Mounting {folder} via {server_url}...")

    try:
        asyncio_run(run_agent_loop(server_url, folder, name, password_hash, ttl_seconds))
    except KeyboardInterrupt:
        print("Unmounting...")
