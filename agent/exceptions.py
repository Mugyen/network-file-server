"""Agent-specific exception types.

Provides typed exceptions for agent lifecycle events.
"""


class AgentExpiredError(Exception):
    """Raised when the agent's TTL has elapsed and the mount should stop.

    Unlike a connection error, this exception signals intentional expiry —
    the reconnect loop must NOT retry on this exception.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class AgentAuthError(Exception):
    """Raised when owner authentication with the relay fails.

    Signals a configuration/credential problem (bad password, unknown
    relay user, unreachable auth endpoint) — the reconnect loop must NOT
    retry, since retrying with the same bad credentials cannot succeed.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
