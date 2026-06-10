"""Agent WebSocket endpoint — accepts tunnel connections and registers mounts.

Includes mount registration rate limiting via the `limits` library directly
(SlowAPI decorators do not work on WebSocket endpoints), and per-IP mount
cap enforcement.
"""

import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from limits import parse as parse_limit

from accounts import (
    AccessMode,
    GroupNotFoundError,
    Role,
    SubjectType,
    UserNotFoundError,
)
from relay.app.exceptions import InvalidSessionError, MountNotFoundError
from relay.app.services.mount_registry import (
    PolicyEntry,
    generate_mount_code,
)
from relay.app.state import RelayState
from tunnel.connection import TunnelConnection
from tunnel.constants import (
    HEARTBEAT_INTERVAL_S,
    HEARTBEAT_MISSED_LIMIT,
    PROTOCOL_VERSION,
)

logger = logging.getLogger("relay.agent")

router = APIRouter()


async def _handle_agent_control_for_mount(
    msg: dict, mount_code: str, state: RelayState
) -> None:
    """Handle delete_expired_files and keep_expired_files control messages.

    Both message types clear expired TTL records for the mount so the agent
    is not re-prompted on the next reconnect.

    Args:
        msg: Parsed control message dict with at least a "type" key.
        mount_code: The mount code this agent connection is registered under.
        state: The per-app RelayState (file_ttl_db may be unwired in tests).
    """
    msg_type = msg.get("type")
    if msg_type in ("delete_expired_files", "keep_expired_files"):
        if state.file_ttl_db is None:
            # FileTtlDb not initialized (relay running without TTL tracking).
            logger.debug(
                "Ignoring %s for mount=%s — FileTtlDb not initialized", msg_type, mount_code
            )
            return
        code = msg.get("code", mount_code)
        await state.file_ttl_db.delete_expired_for_mount(code)
        logger.info("Processed %s for mount=%s", msg_type, code)


async def _read_agent_auth(
    conn: TunnelConnection, websocket: WebSocket, state: RelayState
):
    """Read+validate the agent_auth handshake frame.

    Returns ``(owner_user_id|None, owner_username|None, AccessMode,
    has_password, list[PolicyEntry])`` on success. On any protocol/auth
    failure it sends an error frame, closes the socket (1008), and
    returns ``None``.
    """
    try:
        msg = await conn.receive_control()
    except Exception:
        # A client that can't complete the handshake is likely not an agent
        # at all (port scanner, wrong protocol) — log and reject.
        logger.warning(
            "Agent handshake failed before agent_auth frame: client=%s",
            websocket.client.host if websocket.client else "unknown",
            exc_info=True,
        )
        await websocket.close(code=1008)
        return None

    if msg.get("type") != "agent_auth":
        await websocket.send_json(
            {"type": "error", "error": "expected agent_auth handshake"}
        )
        await websocket.close(code=1008)
        return None

    agent_version = msg.get("protocol_version")
    if agent_version != PROTOCOL_VERSION:
        # Reject BEFORE registering: a version-skewed agent failing loudly
        # at connect time beats silently dropped frames mid-session.
        await websocket.send_json({
            "type": "error",
            "error": (
                f"protocol version mismatch: agent={agent_version!r} "
                f"relay={PROTOCOL_VERSION}"
            ),
        })
        await websocket.close(code=1008)
        return None

    token = msg.get("token")
    has_password = bool(msg.get("has_password", False))
    raw_allow = msg.get("allowlist", []) or []
    try:
        access_mode = AccessMode(msg.get("access_mode", AccessMode.OPEN.value))
    except ValueError:
        await websocket.send_json({"type": "error", "error": "invalid access_mode"})
        await websocket.close(code=1008)
        return None

    owner_user_id: int | None = None
    owner_username: str | None = None
    if token:
        try:
            owner_user_id = state.require_session().verify_agent_owner_token(token)
            owner_username = (
                await state.require_account_store().get_user_by_id(owner_user_id)
            ).username
        except (InvalidSessionError, UserNotFoundError):
            await websocket.send_json(
                {"type": "error", "error": "invalid owner token"}
            )
            await websocket.close(code=1008)
            return None

    if access_mode == AccessMode.RESTRICTED and owner_user_id is None:
        await websocket.send_json(
            {"type": "error", "error": "restricted mount requires --login"}
        )
        await websocket.close(code=1008)
        return None

    entries: list[PolicyEntry] = []
    store = state.require_account_store() if raw_allow else None
    for item in raw_allow:
        try:
            st = SubjectType(item["subject_type"])
            ref = str(item["subject_ref"])
            role = Role(item["role"])
        except (KeyError, ValueError, TypeError):
            await websocket.send_json(
                {"type": "error", "error": "malformed allowlist entry"}
            )
            await websocket.close(code=1008)
            return None
        try:
            if st is SubjectType.USER:
                subject_id = (await store.get_user_by_username(ref)).id
            else:
                subject_id = (await store.get_group_by_name(ref)).id
        except (UserNotFoundError, GroupNotFoundError):
            await websocket.send_json(
                {
                    "type": "error",
                    "error": f"unknown {st.value} {ref!r} in allowlist",
                }
            )
            await websocket.close(code=1008)
            return None
        entries.append(
            PolicyEntry(subject_type=st, subject_id=subject_id, role=role)
        )

    return owner_user_id, owner_username, access_mode, has_password, entries


@router.websocket("/agent/ws")
async def agent_websocket(
    websocket: WebSocket,
    code: str | None = Query(None),
    ttl: int | None = Query(None),
) -> None:
    """Accept an agent WebSocket connection and manage its tunnel lifecycle.

    Order of checks (all before the main accept/register flow):
    1. Extract agent IP from headers (available before accept).
    2. Get config.
    3. Check mount registration rate limit (limits library).
    4. If rate limited: accept, send error, close, return.
    5. Hit rate limit counter (consume token).
    6. Check per-IP mount cap (registry query).
    7. If at cap: accept, send error, close, return.
    8. Accept WebSocket.
    9. Determine code, compute TTL, register, send mount_registered, run loop.

    Args:
        websocket: The FastAPI WebSocket connection from the agent.
        code:      Optional preferred mount code -- reused for reconnect if available.
                   If None or already occupied, a fresh code is generated.
        ttl:       Optional TTL in seconds. Capped to config.max_ttl_seconds.
                   If None, config.max_ttl_seconds is used.
    """
    # Extract agent IP from X-Forwarded-For (Cloud Run) or direct connection
    forwarded: str | None = websocket.headers.get("x-forwarded-for")
    if forwarded:
        client_ip: str = forwarded.split(",")[0].strip()
    else:
        client_ip = websocket.client.host if websocket.client else "unknown"

    state: RelayState = websocket.app.state.relay
    config = state.config
    registry = state.require_registry()

    # --- Reserved code check (before rate limit to avoid wasting tokens) ---
    if code is not None and code == config.dropbox_code:
        logger.warning(
            "Agent tried to register reserved drop box code: client=%s code=%s",
            client_ip, code,
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Reserved mount code",
        })
        await websocket.close(code=1008)
        return

    # --- Rate limit check (before accepting WebSocket) ---
    mount_limit = parse_limit(config.mount_reg_rate)
    if not state.mount_reg_limiter.test(mount_limit, "mount_reg", client_ip):
        logger.warning(
            "Mount registration rate limited: client=%s", client_ip
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Rate limit exceeded",
            "retry_after": 3600,
        })
        await websocket.close(code=1008)
        return

    # Consume a rate limit token
    state.mount_reg_limiter.hit(mount_limit, "mount_reg", client_ip)

    # --- Per-IP mount cap check ---
    current_count: int = await registry.count_mounts_by_ip(client_ip)
    if current_count >= config.max_mounts_per_ip:
        logger.warning(
            "Mount cap exceeded: client=%s count=%d",
            client_ip,
            current_count,
        )
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "error": "Too many active mounts",
            "max": config.max_mounts_per_ip,
        })
        await websocket.close(code=1008)
        return

    # --- Normal mount registration flow ---
    await websocket.accept()

    conn = TunnelConnection(websocket)

    # Owner/policy handshake (exactly one agent_auth frame, before register).
    auth = await _read_agent_auth(conn, websocket, state)
    if auth is None:
        return
    owner_user_id, owner_username, access_mode, has_password, policy_entries = auth

    # Determine assigned code with reclaim-aware logic
    reclaimed: bool = False
    remaining_ttl: int | None = None

    if code is not None:
        reclaim_result = None
        # Owners may reconnect from a new IP — try owner reclaim first.
        if owner_user_id is not None:
            reclaim_result = await registry.try_reclaim_as_owner(
                code, conn, owner_user_id
            )
        if reclaim_result is None:
            reclaim_result = await registry.try_reclaim(code, conn, client_ip)
        if reclaim_result is not None:
            assigned_code = code
            reclaimed = True
            remaining_ttl = reclaim_result.remaining_ttl
        elif not await registry.has_mount(code):
            assigned_code = code
        else:
            assigned_code = generate_mount_code()
    else:
        assigned_code = generate_mount_code()

    # For non-reclaimed mounts: compute TTL and register
    if not reclaimed:
        effective_ttl: int = min(ttl, config.max_ttl_seconds) if ttl is not None else config.max_ttl_seconds
        now: float = time.time()
        expires_at: float = now + effective_ttl

        await registry.register(
            assigned_code,
            conn,
            agent_ip=client_ip,
            created_at=now,
            expires_at=expires_at,
        )
        expires_in: int = effective_ttl
    else:
        effective_ttl = remaining_ttl if remaining_ttl is not None else 0
        expires_in = effective_ttl

    # Persist owner + access policy for both fresh and reclaimed mounts.
    try:
        await registry.set_owner_policy(
            assigned_code,
            owner_user_id,
            access_mode,
            has_password,
            policy_entries,
        )
    except MountNotFoundError:
        logger.warning(
            "set_owner_policy: mount %s missing after register", assigned_code
        )

    reused_code: bool = code is not None and assigned_code == code
    logger.info(
        "Agent connected: code=%s preferred_reuse=%s reclaimed=%s client=%s "
        "ttl=%d owner=%s access=%s",
        assigned_code,
        reused_code,
        reclaimed,
        client_ip,
        effective_ttl,
        owner_username,
        access_mode.value,
    )
    await conn.send_control({
        "type": "mount_registered",
        "code": assigned_code,
        "ttl": effective_ttl,
        "expires_in": expires_in,
        "reclaimed": reclaimed,
        "remaining_ttl": remaining_ttl,
        "owner": owner_username,
    })
    # Send expired files list to agent on reclaim so it can prompt user
    if reclaimed:
        if state.file_ttl_db is None:
            # FileTtlDb not initialized (relay running without TTL tracking).
            logger.debug(
                "Skipping expired-files prompt for mount=%s — FileTtlDb not initialized",
                assigned_code,
            )
        else:
            expired = await state.file_ttl_db.get_expired_for_mount(assigned_code)
            if expired:
                await conn.send_control({
                    "type": "expired_files",
                    "code": assigned_code,
                    "files": [{"path": fp, "expired_at": exp} for fp, exp in expired],
                })

    async def _on_agent_control(msg: dict) -> None:
        """Handle application-specific control messages from the agent.

        delete_expired_files: agent deleted expired files, clear TTL records.
        keep_expired_files: user chose to keep files, clear TTL records so
        they are not re-prompted on next reconnect.
        """
        await _handle_agent_control_for_mount(msg, assigned_code, state)

    conn.set_control_handler(_on_agent_control)
    conn.start_heartbeat(HEARTBEAT_INTERVAL_S, HEARTBEAT_MISSED_LIMIT)
    try:
        await conn.run_receive_loop()
    except WebSocketDisconnect:
        pass
    finally:
        logger.info("Agent disconnected: code=%s", assigned_code)
        await conn.close()
        try:
            await registry.mark_offline(assigned_code)
        except MountNotFoundError:
            # Mount already deregistered (e.g. explicitly removed) — fine.
            logger.debug("mark_offline skipped — mount %s already gone", assigned_code)
