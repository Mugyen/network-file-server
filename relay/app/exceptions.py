class MountNotFoundError(Exception):
    """Raised when a mount code is not present in the registry.

    Stores the code that was not found for logging and HTTP response purposes.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"No mount registered with code '{code}'")


class MountOfflineError(Exception):
    """Raised when a mount exists but its status is OFFLINE.

    Stores the code for HTTP response purposes.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mount '{code}' is currently offline")


class MountExpiredError(Exception):
    """Raised when a mount exists but its status is EXPIRED.

    Stores the code for HTTP response purposes.
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Mount '{code}' has expired")
