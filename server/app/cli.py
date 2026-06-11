"""CLI entry point for the Network File Server.

Provides main() for argparse-based CLI and run_with_defaults() convenience function.
Supports two modes:
  - LAN mode (default): network-file-server <folder> [options]
  - Mount mode: network-file-server mount <folder> --server <url>

Subcommand detection: _parse_args() inspects argv[0] for known subcommands.
When 'mount' is detected, the mount parser is used directly. Otherwise, the LAN
parser handles the invocation. This avoids argparse's positional-vs-subparser
conflict where nargs='?' would greedily consume 'mount' as the folder argument.
"""

import argparse
import sys
from typing import Optional

from shared.duration import parse_duration

# Known subcommand names — used to detect mode in _parse_args and main()
_SUBCOMMANDS: frozenset = frozenset({"mount"})


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the LAN-mode argument parser.

    This parser handles the default invocation:
      network-file-server <folder> [--port PORT] [--host HOST] [--password PW]
                                   [--read-only] [--receive]

    It does NOT include mount subcommand parsing. Mount is handled separately
    by _build_mount_parser() and _parse_args() which routes based on argv.

    Backward compatibility: existing server tests call _build_parser() directly
    and expect LAN-mode arg parsing. Those tests continue to work unchanged.
    """
    parser = argparse.ArgumentParser(
        description="Network File Server - Share files over local network"
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

    Handles: network-file-server mount <folder> --server <url> [--name NAME]
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
    parser.add_argument(
        "--login",
        help="Relay username that owns this mount (enables account access control)",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        dest="password_stdin",
        help="Read the relay owner password from stdin instead of prompting",
    )
    parser.add_argument(
        "--access-mode",
        choices=["open", "restricted"],
        dest="access_mode",
        help="open = anyone may access; restricted = only allowlisted accounts "
        "(default: restricted when --login is given)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        help="Allowlist entry 'type:ref:role' (e.g. user:alice:write, "
        "group:eng:read). Repeatable.",
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
            login=mount_args.login,
            password_stdin=mount_args.password_stdin,
            access_mode=mount_args.access_mode,
            allow=mount_args.allow,
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

    Parsing lives here; composition (building/serving the app, wiring the
    agent) lives in server/app/bootstrap.py so it can be tested without argv.
    """
    args = _parse_args()

    # Imported here so `import server.app.cli` does not pull in the agent
    # package — bootstrap is the single composition root that does.
    from server.app import bootstrap

    if args.command == "mount":
        bootstrap.run_mount_agent(args)
        return

    bootstrap.run_lan_server(args)


def run_with_defaults(folder: str) -> None:
    """Start the server with default port 8000 and host 0.0.0.0.

    Convenience function for programmatic use.
    Port 8000: FastAPI convention.
    Host 0.0.0.0: Binds to all interfaces for LAN access.
    """
    sys.argv = ["network-file-server", folder]
    main()


if __name__ == "__main__":
    main()
