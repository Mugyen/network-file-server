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


class AccessRequestNotFoundError(Exception):
    """Raised when an access-request id is not present."""

    def __init__(self, request_id: int) -> None:
        self.request_id = request_id
        super().__init__(f"No access request with id {request_id}")


class InvalidSessionError(Exception):
    """Raised when a relay session cookie is missing, malformed, or expired."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid relay session: {reason}")


class AuthenticationRequiredError(Exception):
    """Raised when access requires login but the requester is anonymous.

    The proxy translates this into a 302 redirect to the relay login page
    (or a 401 for XHR clients).
    """

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Authentication required to access mount '{code}'")


class AccessDeniedError(Exception):
    """Raised when an authenticated user is not allowed to access a mount.

    The proxy translates this into a 403 page.
    """

    def __init__(self, code: str, username: str) -> None:
        self.code = code
        self.username = username
        super().__init__(
            f"User '{username}' is not permitted to access mount '{code}'"
        )
