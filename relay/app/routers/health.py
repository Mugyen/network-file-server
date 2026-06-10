"""Health check endpoint for Cloud Run liveness probes."""

from fastapi import APIRouter, Request

from relay.app.dependencies import get_relay_state

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    """Return relay health status with active mount count.

    Returns:
        A dict with 'status' ('ok') and 'mounts' (total mount count).
    """
    registry = get_relay_state(request).require_registry()
    count: int = await registry.mount_count()
    return {"status": "ok", "mounts": count}
