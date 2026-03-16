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
