class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected.

    The attempted path is included in the error message for logging purposes.
    """

    def __init__(self, attempted_path: str) -> None:
        self.attempted_path = attempted_path
        super().__init__(
            f"Path traversal detected: attempted to access '{attempted_path}'"
        )
