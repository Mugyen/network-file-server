"""Password hashing/verification — the single home for credential crypto.

bcrypt-based, constant-time verification. Other packages (server, relay)
must reuse these functions rather than re-implementing bcrypt logic.
"""

import bcrypt

from accounts.exceptions import WeakPasswordError

# bcrypt silently truncates inputs longer than 72 bytes; reject instead.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> bytes:
    """Hash a plaintext password using bcrypt.

    Raises:
        WeakPasswordError: password is empty or exceeds 72 UTF-8 bytes.
    """
    if len(plain_password) == 0:
        raise WeakPasswordError("Password must not be empty")
    if len(plain_password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise WeakPasswordError(
            f"Password must not exceed {_BCRYPT_MAX_BYTES} bytes (bcrypt limit)"
        )
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    """Verify a plaintext password against a bcrypt hash (constant-time).

    Raises:
        WeakPasswordError: plain_password is empty.
        ValueError: hashed_password is empty.
    """
    if len(plain_password) == 0:
        raise WeakPasswordError("Password must not be empty")
    if len(hashed_password) == 0:
        raise ValueError("hashed_password must not be empty")
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)
