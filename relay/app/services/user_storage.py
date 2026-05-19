"""Per-user relay-hosted storage — isolated dir + byte quota.

Each registered user gets an isolated directory on the relay's disk under
``<data_dir>/users/<user_id>``. A per-user byte quota (admin override in
the accounts store, else the relay default) is enforced on upload.

Files served through tunnel-backed mounts live on the agent's machine and
are NOT metered here — only relay-hosted storage is.
"""

import os
from pathlib import Path

from accounts import QuotaNotSetError
from relay.app.config import get_config
from relay.app.services.account_store import get_account_store


def user_dir(user_id: int) -> Path:
    """Return (creating if needed) the isolated storage dir for a user."""
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive int")
    path = Path(get_config().data_dir) / "users" / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def usage_bytes(user_id: int) -> int:
    """Total bytes stored by a user (recursive sum of regular files)."""
    root = user_dir(user_id)
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
            except OSError:
                # File vanished mid-walk — skip; do not abort accounting.
                continue
    return total


async def quota_bytes(user_id: int) -> int:
    """Effective quota: per-user override if set, else the relay default."""
    try:
        return await get_account_store().get_user_quota(user_id)
    except QuotaNotSetError:
        return get_config().default_user_quota_bytes


async def remaining_bytes(user_id: int) -> int:
    """Bytes the user may still store (never negative)."""
    return max(0, await quota_bytes(user_id) - usage_bytes(user_id))
