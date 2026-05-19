"""Global singleton accessor for the relay's AccountStore.

The relay holds exactly one account store (the user/group registry shared
across all mounts). Installed by the app lifespan; read by routers and the
proxy enforcement layer.
"""

from accounts import AccountStore

_account_store: AccountStore | None = None


def get_account_store() -> AccountStore:
    """Return the global AccountStore.

    Raises:
        RuntimeError: If set_account_store() has not been called.
    """
    if _account_store is None:
        raise RuntimeError(
            "AccountStore has not been set. Call set_account_store() first."
        )
    return _account_store


def set_account_store(store: AccountStore | None) -> None:
    """Install (or clear) the global AccountStore singleton."""
    global _account_store
    _account_store = store
