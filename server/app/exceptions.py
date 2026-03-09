class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected.

    The attempted path is included in the error message for logging purposes.
    """

    def __init__(self, attempted_path: str) -> None:
        self.attempted_path = attempted_path
        super().__init__(
            f"Path traversal detected: attempted to access '{attempted_path}'"
        )


class FileConflictError(Exception):
    """Raised when a file operation conflicts with an existing file or folder.

    Stores both the path being operated on and the existing path that conflicts.
    """

    def __init__(self, path: str, existing_path: str) -> None:
        self.path = path
        self.existing_path = existing_path
        super().__init__(
            f"Conflict: '{path}' already exists at '{existing_path}'"
        )


class InvalidFileNameError(Exception):
    """Raised when a file or folder name is invalid.

    Stores the invalid name and the reason it was rejected.
    """

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Invalid file name '{name}': {reason}")
