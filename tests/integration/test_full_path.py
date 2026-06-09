"""Full-path integration: browser→relay→tunnel→agent→server, in one process.

Boots a real relay (uvicorn on a random port), connects a real agent over a
real WebSocket using the production composition root (build_mount_app), and
exercises the complete proxy path with plain HTTP/WS clients:

- browse (GET /m/{code}/api/files)
- upload (multipart POST through the tunnel)
- download (streamed response back through the tunnel)
- WebSocket bridging (ping→pong + server-pushed device_list)

This is the product's core promise, previously verified only by hand or
via the browser-level Playwright suite.
"""

import asyncio
import json
import secrets
import uuid

import httpx
import pytest
import pytest_asyncio
import uvicorn
import websockets

from agent.connection import connect_and_serve
from relay.app.enums import MountStatus
from server.app.cli import build_mount_app

# Generous CI-friendly timeout for each await step.
STEP_TIMEOUT_S = 15.0


# One stack for the whole module: pytest-asyncio tears down per-test loops in
# a way that strands aiosqlite worker threads when the relay boots repeatedly
# in one process; a single module-scoped boot+teardown exits cleanly (and is
# 3x faster). Tests are read/write-isolated by using distinct file names.
@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def full_stack(tmp_path_factory: pytest.TempPathFactory):
    """A live relay (uvicorn, random port) + a connected agent mount.

    Yields (base_url, mount_code, shared_folder).
    """
    tmp_path = tmp_path_factory.mktemp("full-path")
    mp = pytest.MonkeyPatch()
    mp.setenv("RELAY_SESSION_SECRET", secrets.token_urlsafe(16))
    mp.setenv("RELAY_DB_PATH", str(tmp_path / "mounts.db"))
    mp.setenv("RELAY_ACCOUNTS_DB_PATH", str(tmp_path / "accounts.db"))
    mp.setenv("RELAY_DATA_DIR", str(tmp_path / "data"))

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "seeded.txt").write_text("full path payload")

    # The relay process-global registry is set by the app lifespan; reset it
    # afterwards so other tests are unaffected.
    from relay.app.main import create_relay_app

    relay_app = create_relay_app()
    config = uvicorn.Config(relay_app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(STEP_TIMEOUT_S):
            while not server.started:
                await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"

        # Real agent over a real WebSocket, using the production factory.
        agent_task = asyncio.create_task(
            connect_and_serve(
                relay_url=base_url,
                folder=shared,
                name="integration",
                preferred_code=None,
                password_hash=None,
                ttl_seconds=None,
                owner=None,
                app_factory=build_mount_app,
            )
        )

        # The lifespan installed the registry singleton; poll it for the
        # agent's assigned code (dropbox registers too — skip it).
        from relay.app.config import get_config
        from relay.app.services.mount_registry import get_registry

        dropbox_code = get_config().dropbox_code
        registry = get_registry()
        code: str | None = None
        async with asyncio.timeout(STEP_TIMEOUT_S):
            while code is None:
                for mount in await registry.active_mounts():
                    if mount.code != dropbox_code and mount.status is MountStatus.ONLINE:
                        code = mount.code
                await asyncio.sleep(0.05)

        try:
            yield base_url, code, shared
        finally:
            # The agent's receive loop gathers in-flight handler tasks in its
            # finally block WITHOUT cancelling them, so a single cancel can
            # hang there — bound the await and re-cancel if needed.
            agent_task.cancel()
            try:
                async with asyncio.timeout(5):
                    await agent_task
            except (TimeoutError, asyncio.CancelledError, Exception):
                pass  # Teardown — the task ends by cancellation by design.
    finally:
        server.should_exit = True
        async with asyncio.timeout(STEP_TIMEOUT_S):
            await server_task
        mp.undo()
        # Sweep any straggler tasks (agent handlers, tunnel internals) so the
        # pytest-asyncio loop finalizer doesn't wait on them forever. A second
        # cancel breaks tasks stuck in their own finally-gathers.
        stragglers = [
            t for t in asyncio.all_tasks() if t is not asyncio.current_task()
        ]
        for task in stragglers:
            task.cancel()
        if stragglers:
            try:
                async with asyncio.timeout(5):
                    await asyncio.gather(*stragglers, return_exceptions=True)
            except TimeoutError:
                # Truly stuck tasks: report rather than hang the whole run.
                still = [t for t in stragglers if not t.done()]
                raise RuntimeError(f"straggler tasks did not exit: {still!r}")


@pytest.mark.asyncio(loop_scope="module")
async def test_browse_through_tunnel(full_stack) -> None:
    base_url, code, _shared = full_stack
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.get(f"/m/{code}/api/files?path=")
        assert response.status_code == 200
        names = [e["name"] for e in response.json()["entries"]]
        assert "seeded.txt" in names


@pytest.mark.asyncio(loop_scope="module")
async def test_upload_then_download_through_tunnel(full_stack) -> None:
    base_url, code, shared = full_stack
    blob = b"tunnel round trip " + uuid.uuid4().hex.encode()

    async with httpx.AsyncClient(base_url=base_url) as client:
        up = await client.post(
            f"/m/{code}/api/files/upload?path=&ttl=0",
            files={"files": ("roundtrip.bin", blob, "application/octet-stream")},
        )
        assert up.status_code == 200

        # The file physically landed in the agent's shared folder.
        assert (shared / "roundtrip.bin").read_bytes() == blob

        # And streams back out through the tunnel byte-identically.
        down = await client.get(f"/m/{code}/api/files/download?path=roundtrip.bin")
        assert down.status_code == 200
        assert down.content == blob


@pytest.mark.asyncio(loop_scope="module")
async def test_websocket_bridges_through_tunnel(full_stack) -> None:
    """WS upgrade through relay→tunnel→agent→server: the server pushes
    device_list (server→browser direction) and answers ping with pong
    (browser→server direction)."""
    base_url, code, _shared = full_stack
    ws_url = (
        base_url.replace("http://", "ws://")
        + f"/m/{code}/ws?device_name=Integration&device_id=int-test-1"
    )

    async with websockets.connect(ws_url, open_timeout=STEP_TIMEOUT_S) as ws:
        async with asyncio.timeout(STEP_TIMEOUT_S):
            first = json.loads(await ws.recv())
            assert first["type"] == "device_list"
            assert first["your_device_id"] == "int-test-1"

            await ws.send(json.dumps({"type": "ping"}))
            # Skip unrelated broadcasts (device_count etc.) until pong.
            while True:
                message = json.loads(await ws.recv())
                if message["type"] == "pong":
                    break
