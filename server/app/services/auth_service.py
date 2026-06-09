"""Authentication service for password hashing and session token management.

Provides bcrypt-based password hashing/verification and itsdangerous-based
signed session tokens for cookie authentication.
"""

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from accounts.exceptions import WeakPasswordError
from accounts.passwords import (
    hash_password as _hash_password,
    verify_password as _verify_password,
)


def hash_password(plain_password: str) -> bytes:
    """Hash a plaintext password using bcrypt."""
    try:
        return _hash_password(plain_password)
    except WeakPasswordError as exc:
        raise ValueError(str(exc)) from exc


def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return _verify_password(plain_password, hashed_password)
    except WeakPasswordError as exc:
        raise ValueError(str(exc)) from exc


class AuthTokenService:
    """Creates and validates signed session tokens using itsdangerous.

    Each instance uses its own secret key, so tokens from one instance
    are rejected by another (e.g., after server restart with new key).
    """

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key)

    def create_token(self) -> str:
        """Create a new signed session token."""
        return self._serializer.dumps({"authenticated": True})

    def validate_token(self, token: str) -> bool:
        """Validate a session token. Returns False for invalid/expired tokens."""
        try:
            self._serializer.loads(token)
            return True
        except (BadSignature, SignatureExpired):
            return False

