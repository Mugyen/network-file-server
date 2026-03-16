"""Health check endpoint for Cloud Run liveness probes."""

from fastapi import APIRouter

from relay.app.services.mount_registry import get_registry

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    """Return relay health status with active mount count.

    Returns:
        A dict with 'status' ('ok') and 'mounts' (active mount count).
    """
    registry = get_registry()
    return {"status": "ok", "mounts": len(registry._mounts)}
