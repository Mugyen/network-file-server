"""Per-user relay-hosted storage — isolated dir + byte quota.

Each registered user gets an isolated directory on the relay's disk under
``<data_dir>/users/<user_id>``. A per-user byte quota (admin override in
the accounts store, else the relay default) is enforced on upload.

Files served through tunnel-backed mounts live on the agent's machine and
are NOT metered here — only relay-hosted storage is.
"""

import os
from pathlib import Path

from accounts import AccountStore, QuotaNotSetError


def user_dir(data_dir: Path, user_id: int) -> Path:
    """Return (creating if needed) the isolated storage dir for a user."""
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("user_id must be a positive int")
    path = data_dir / "users" / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def usage_bytes(data_dir: Path, user_id: int) -> int:
    """Total bytes stored by a user (recursive sum of regular files)."""
    root = user_dir(data_dir, user_id)
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


async def quota_bytes(
    account_store: AccountStore, default_quota_bytes: int, user_id: int
) -> int:
    """Effective quota: per-user override if set, else the relay default."""
    try:
        return await account_store.get_user_quota(user_id)
    except QuotaNotSetError:
        return default_quota_bytes


async def remaining_bytes(
    data_dir: Path,
    account_store: AccountStore,
    default_quota_bytes: int,
    user_id: int,
) -> int:
    """Bytes the user may still store (never negative)."""
    quota = await quota_bytes(account_store, default_quota_bytes, user_id)
    return max(0, quota - usage_bytes(data_dir, user_id))
