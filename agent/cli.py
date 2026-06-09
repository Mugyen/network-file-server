"""Agent CLI entry point — mount subcommand for remote relay sharing.

Provides run_mount() which is called from server/app/cli.py when the user
invokes `network-file-server mount <folder> --server <url>`.
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from accounts import AccessMode
from accounts.exceptions import WeakPasswordError
from accounts.passwords import hash_password
from agent.auth import AgentOwner, parse_allow_entry
from agent.connection import AppFactory, run_agent_loop

# Alias for patching in tests
asyncio_run = asyncio.run


def run_mount(args: argparse.Namespace, app_factory: AppFactory) -> None:
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
        app_factory: Builds the local ASGI app for the mount (supplied by the
              composition root, e.g. server/app/cli.py — the agent package
              itself has no dependency on any specific app).

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
        try:
            password_hash = hash_password(args.password)
        except WeakPasswordError as exc:
            print(f"Error: {exc}")
            sys.exit(1)

    ttl_seconds: int | None = args.ttl_seconds

    name: str = args.name if args.name is not None else folder.name
    server_url: str = args.server

    owner: AgentOwner | None = _build_owner(args, server_url)

    print(f"Mounting {folder} via {server_url}...")

    try:
        asyncio_run(
            run_agent_loop(
                server_url, folder, name, password_hash, ttl_seconds, owner, app_factory
            )
        )
    except KeyboardInterrupt:
        print("Unmounting...")


def _build_owner(args: argparse.Namespace, server_url: str) -> AgentOwner | None:
    """Construct an AgentOwner from --login/--access-mode/--allow, or None.

    Exits(1) on misconfiguration (restricted without login, bad --allow,
    missing owner password).
    """
    login: str | None = getattr(args, "login", None)
    access_mode_arg: str | None = getattr(args, "access_mode", None)

    if login is None:
        if access_mode_arg == AccessMode.RESTRICTED.value:
            print("Error: --access-mode restricted requires --login")
            sys.exit(1)
        return None

    if getattr(args, "password_stdin", False):
        owner_password = sys.stdin.readline().rstrip("\n")
    else:
        owner_password = getpass.getpass(f"Relay password for '{login}': ")
    if not owner_password:
        print("Error: an owner password is required with --login")
        sys.exit(1)

    # Default to RESTRICTED when an owner logs in (the point of logging in
    # is usually to restrict access); --access-mode can override.
    access_mode = (
        AccessMode(access_mode_arg)
        if access_mode_arg is not None
        else AccessMode.RESTRICTED
    )

    try:
        allowlist = tuple(
            parse_allow_entry(spec) for spec in (getattr(args, "allow", None) or [])
        )
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    return AgentOwner(
        username=login,
        password=owner_password,
        access_mode=access_mode,
        allowlist=allowlist,
    )
