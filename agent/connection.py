"""Agent connection loop with WebSocket reconnect and OPEN frame dispatch.

Provides connect_and_serve (single connection attempt) and run_agent_loop
(outer reconnect loop with exponential backoff).
"""

import asyncio
import functools
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from httpx import ASGITransport
from websockets.asyncio.client import connect as websockets_connect
from websockets.exceptions import ConnectionClosed

from accounts import AccessMode
from agent.auth import AgentOwner, fetch_agent_token
from agent.exceptions import AgentAuthError, AgentExpiredError
from agent.proxy import handle_open_frame, handle_ws_open_frame
from agent.ws_adapter import WebSocketClientAdapter
from shared.backoff import compute_backoff
from agent.display import print_connected_status, print_mounted, print_reconnect_status
from tunnel.connection import TunnelConnection
from tunnel.constants import (
    AGENT_HEARTBEAT_INTERVAL_S,
    HEARTBEAT_MISSED_LIMIT,
    PROTOCOL_VERSION,
)
from tunnel.exceptions import MetadataError
from tunnel.metadata import RequestMetadata, WsOpenMetadata

import logging

logger = logging.getLogger("agent.connection")

# Alias for patching in tests
asyncio_sleep = asyncio.sleep


async def _reject_open(conn: TunnelConnection, request_id: uuid.UUID) -> None:
    """Answer a malformed OPEN with an HTTP 400 so the relay's request resolves.

    Best-effort: a send failure here means the connection is going down
    anyway and the relay's first-byte timeout will produce the 504.
    """
    try:
        await conn.send_data(
            request_id,
            json.dumps({"status": 400, "headers": {}}).encode("utf-8"),
        )
        await conn.send_close(request_id)
    except Exception as exc:  # noqa: BLE001 — best-effort by contract; logged, never raised
        logger.debug("Could not deliver 400 for malformed OPEN: %r", exc)


@dataclass(frozen=True)
class MountAppContext:
    """Everything an app factory needs to build the local ASGI app for a mount.

    The agent knows nothing about the application it tunnels — the CLI glue
    layer supplies a factory that turns this context into an ASGI app. This
    keeps the agent package free of server imports (it tunnels anything
    that speaks ASGI).
    """

    folder: Path
    password_hash: bytes | None
    mount_code: str
    relay_url: str
    # Per-mount secret the relay uses to sign injected identity headers and
    # the embedded server uses to verify them (see shared.identity_sig).
    identity_secret: str


AppFactory = Callable[[MountAppContext], Any]


class _OpenFrameHandlers:
    """Spawns + tracks per-request handler tasks for the agent receive loop.

    Wires OPEN/WS_OPEN frames (delivered by
    ``TunnelConnection.run_receive_loop_with_handlers``) to the HTTP and
    WebSocket proxy handlers, tracking the spawned tasks so they can be
    drained on shutdown. This replaces the agent's former hand-rolled receive
    loops that poked ``conn._ws``/``conn._dispatch_frame`` directly.
    """

    def __init__(
        self,
        conn: TunnelConnection,
        asgi_client: httpx.AsyncClient,
        app: object,
    ) -> None:
        self._conn = conn
        self._asgi_client = asgi_client
        self._app = app
        self._pending: set[asyncio.Task] = set()

    def _track(self, task: asyncio.Task) -> None:
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def on_open(self, request_id: uuid.UUID, payload: bytes) -> None:
        """Spawn an HTTP request handler for an OPEN frame."""
        try:
            metadata = RequestMetadata.from_payload(payload)
        except MetadataError as exc:
            # Malformed OPEN must not kill the receive loop — answer 400 so
            # the relay's waiting request resolves.
            logger.warning("Rejected malformed OPEN metadata: %s", exc)
            await _reject_open(self._conn, request_id)
            return
        # Open the stream BEFORE spawning so DATA frames dispatched by later
        # loop iterations land in the queue instead of being dropped.
        self._conn.open_stream(request_id)
        self._track(asyncio.create_task(
            handle_open_frame(self._conn, request_id, metadata, self._asgi_client)
        ))

    async def on_ws_open(self, request_id: uuid.UUID, payload: bytes) -> None:
        """Spawn a WebSocket bridge handler for a WS_OPEN frame."""
        try:
            ws_metadata = WsOpenMetadata.from_payload(payload)
        except MetadataError as exc:
            logger.warning("Rejected malformed WS_OPEN metadata: %s", exc)
            await self._conn.send_ws_close(request_id)
            return
        # Match HTTP OPEN ordering: register before spawning so immediately
        # following WS_DATA frames are queued for the bridge instead of dropped.
        self._conn.open_stream(request_id)
        self._track(asyncio.create_task(
            handle_ws_open_frame(self._conn, request_id, ws_metadata, self._app)
        ))

    async def drain(self) -> None:
        """Await in-flight handler tasks; cancel them first if shutting down.

        On cancellation (Ctrl+C / TTL teardown) a handler blocked on a body
        frame that will never arrive would otherwise hang the agent's
        shutdown forever, so cancel before gathering.
        """
        if not self._pending:
            return
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            for task in self._pending:
                task.cancel()
        await asyncio.gather(*self._pending, return_exceptions=True)


def _make_agent_control_handler(
    conn: TunnelConnection,
) -> Callable[[dict], Awaitable[None]]:
    """Return a control-message handler for relay→agent control frames."""

    async def _handle(message: dict) -> None:
        if message.get("type") == "expired_files":
            await _handle_expired_files(conn, message)

    return _handle


async def _handle_expired_files(conn: TunnelConnection, message: dict) -> None:
    """Handle expired_files control message from relay — prompt user to keep or delete."""
    expired_list: list[dict] = message.get("files", [])
    if not expired_list:
        return

    print(f"\n{len(expired_list)} file(s) have expired TTLs:")
    for f in expired_list:
        print(f"  - {f['path']}")

    loop = asyncio.get_running_loop()
    answer: str = await loop.run_in_executor(
        None,
        functools.partial(input, "Delete expired files? [y/N]: "),
    )

    if answer.strip().lower() == "y":
        await conn.send_control({
            "type": "delete_expired_files",
            "code": message.get("code", ""),
        })
        print("Requested deletion of expired files.")
    else:
        await conn.send_control({
            "type": "keep_expired_files",
            "code": message.get("code", ""),
        })
        print("Keeping expired files.")


def _format_remaining(seconds: int) -> str:
    """Format remaining seconds as human-readable duration string.

    Args:
        seconds: Remaining time in seconds (must be positive).

    Returns:
        Formatted string like "1h 30m", "5m", or "30s".
    """
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s" if secs > 0 else f"{minutes}m"
    return f"{secs}s"


async def _print_ttl_countdown(ttl_seconds: int) -> None:
    """Print remaining TTL to terminal, starting immediately.

    Prints on first call, then every 10 seconds for short TTLs (<= 5 min)
    or every 60 seconds for longer TTLs.

    Args:
        ttl_seconds: Total TTL duration in seconds.
    """
    interval = 10 if ttl_seconds <= 300 else 60
    start = time.monotonic()

    # Print immediately on start
    print(f"Expires in {_format_remaining(ttl_seconds)}")

    while True:
        await asyncio.sleep(interval)
        elapsed = int(time.monotonic() - start)
        remaining = ttl_seconds - elapsed
        if remaining <= 0:
            return
        print(f"Expires in {_format_remaining(remaining)}")


async def connect_and_serve(
    relay_url: str,
    folder: Path,
    name: str,
    preferred_code: str | None,
    password_hash: bytes | None,
    ttl_seconds: int | None,
    owner: AgentOwner | None,
    app_factory: AppFactory,
) -> str:
    """Connect to the relay WebSocket, register a mount, and serve requests.

    Connects to {relay_url}/agent/ws (with optional ?code=preferred_code for
    reconnect), registers the mount, starts heartbeat, creates local ASGI client,
    then enters the agent receive loop to dispatch OPEN frames.

    When ttl_seconds is not None, a TTL countdown task is created that closes
    the connection after the duration elapses. After the receive loop exits, an
    AgentExpiredError is raised if TTL fired, signaling the outer loop to NOT retry.

    Args:
        relay_url:      Base URL of the relay server (e.g. 'https://relay.example.com').
        folder:         Local folder to share (must exist and be a directory).
        name:           Human-readable name for the mount.
        preferred_code: Mount code to request on reconnect; None for first connect.
        password_hash:  bcrypt hash for protecting the remote mount; None for open access.
        ttl_seconds:    Auto-expire duration in seconds; None disables TTL.
        app_factory:    Builds the local ASGI app from a MountAppContext once
                        the mount code is assigned (dependency inversion — the
                        agent has no knowledge of the server package).

    Returns:
        The assigned mount code (for use as preferred_code on next reconnect).

    Raises:
        AgentExpiredError: If the TTL elapsed and the mount should not reconnect.
        ValueError: If the first control message is not of type 'mount_registered'.
    """
    # Convert http(s):// to ws(s):// — websockets library requires ws/wss scheme
    base = relay_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    ws_url = f"{base}/agent/ws"
    if preferred_code is not None:
        ws_url = f"{ws_url}?code={preferred_code}"

    # ping_interval=None disables websockets built-in ping (TunnelConnection handles heartbeat)
    async with websockets_connect(ws_url, ping_interval=None) as raw_ws:
        adapter = WebSocketClientAdapter(raw_ws)
        conn = TunnelConnection(adapter)

        # Per-mount identity-signing secret: minted fresh each connect and
        # shared only with this relay (in agent_auth) and this mount's
        # embedded server (via MountAppContext). A LAN client that reaches
        # the server directly cannot forge signed identity headers.
        identity_secret = secrets.token_urlsafe(32)

        # Owner/policy handshake: the relay reads exactly one agent_auth
        # control message after accepting the socket and before sending
        # mount_registered. Anonymous/open mounts still send it (token=None).
        token: str | None = None
        if owner is not None:
            token = await fetch_agent_token(
                relay_url, owner.username, owner.password
            )
        await conn.send_control({
            "type": "agent_auth",
            "protocol_version": PROTOCOL_VERSION,
            "identity_secret": identity_secret,
            "token": token,
            "access_mode": (
                owner.access_mode.value
                if owner is not None
                else AccessMode.OPEN.value
            ),
            "has_password": password_hash is not None,
            "allowlist": [
                {
                    "subject_type": e.subject_type.value,
                    "subject_ref": e.subject_ref,
                    "role": e.role.value,
                }
                for e in (owner.allowlist if owner is not None else ())
            ],
        })

        control = await conn.receive_control()
        if control.get("type") != "mount_registered":
            raise ValueError(
                f"Expected 'mount_registered' control message, got type={control.get('type')!r}"
            )

        assigned_code: str = control["code"]

        # Mutual heartbeat: the relay pings every HEARTBEAT_INTERVAL_S; the
        # agent pings at a slower cadence so it also detects a half-dead
        # relay socket (otherwise it would believe the mount is online while
        # browsers get 503s). The relay's receive loop answers with pongs.
        conn.start_heartbeat(AGENT_HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)

        print_connected_status(reconnected=preferred_code is not None)
        print_mounted(relay_url, assigned_code, folder, name)

        # Build the local ASGI app via the injected factory — configuration
        # (config globals, auth token service) is the factory's concern.
        app = app_factory(
            MountAppContext(
                folder=folder,
                password_hash=password_hash,
                mount_code=assigned_code,
                relay_url=relay_url,
                identity_secret=identity_secret,
            )
        )
        transport = ASGITransport(app=app)
        asgi_client = httpx.AsyncClient(transport=transport, base_url="http://local")

        ttl_expired = False
        ttl_tasks: list[asyncio.Task] = []

        async def _ttl_countdown(seconds: int) -> None:
            """Sleep for `seconds` then close the connection and mark TTL as expired."""
            nonlocal ttl_expired
            await asyncio.sleep(seconds)
            ttl_expired = True
            await conn.close()

        if ttl_seconds is not None:
            ttl_tasks.append(asyncio.create_task(_ttl_countdown(ttl_seconds)))
            ttl_tasks.append(asyncio.create_task(_print_ttl_countdown(ttl_seconds)))

        handlers = _OpenFrameHandlers(conn, asgi_client, app)
        conn.set_control_handler(_make_agent_control_handler(conn))
        try:
            await conn.run_receive_loop_with_handlers(
                handlers.on_open, handlers.on_ws_open
            )
        except (ConnectionError, ConnectionClosed, EOFError, OSError):
            # Normal WebSocket disconnect — treat as clean exit
            pass
        finally:
            # Drain in-flight request handlers before tearing down (cancel
            # first on shutdown so a handler awaiting a never-arriving body
            # frame cannot hang the agent).
            await handlers.drain()
            for task in ttl_tasks:
                task.cancel()
            await conn.close()
            await asgi_client.aclose()

    if ttl_expired:
        raise AgentExpiredError("Mount expired after TTL")

    return assigned_code


async def run_agent_loop(
    relay_url: str,
    folder: Path,
    name: str,
    password_hash: bytes | None,
    ttl_seconds: int | None,
    owner: AgentOwner | None,
    app_factory: AppFactory,
) -> None:
    """Outer reconnect loop for the agent — retries with exponential backoff on disconnect.

    Calls connect_and_serve in a loop. On success (clean return), resets the
    attempt counter. On exception, increments the attempt counter, computes a
    backoff delay, and retries after sleeping.

    Catches AgentExpiredError and exits WITHOUT retrying — TTL expiry is intentional.
    Tracks the last assigned code across iterations to pass as preferred_code
    on reconnect, allowing the relay to reuse the same mount code.

    Exits when KeyboardInterrupt is raised (Ctrl+C) or AgentExpiredError is raised.

    Args:
        relay_url:     Base URL of the relay server.
        folder:        Local folder to share.
        name:          Human-readable name for the mount.
        password_hash: bcrypt hash for protecting the mount; None for open access.
        ttl_seconds:   Auto-expire duration in seconds; None disables TTL.
        app_factory:   Builds the local ASGI app once a mount code is assigned.
    """
    attempt = 0
    last_code: str | None = None

    while True:
        try:
            last_code = await connect_and_serve(
                relay_url,
                folder,
                name,
                last_code,
                password_hash,
                ttl_seconds,
                owner,
                app_factory,
            )
            # Clean disconnect — reset attempt counter
            attempt = 0
        except AgentExpiredError:
            # TTL expired — do NOT retry, exit cleanly
            print("Mount expired")
            break
        except AgentAuthError as exc:
            # Bad credentials / unreachable auth — retrying cannot help.
            print(f"Owner authentication failed: {exc.message}")
            break
        except KeyboardInterrupt:
            break
        except Exception:
            attempt += 1
            delay = compute_backoff(attempt, 1.0, 60.0, 0.5)
            print_reconnect_status(attempt, delay)
            await asyncio_sleep(delay)
