"""Authentication service for password hashing and session token management.

Provides bcrypt-based password hashing/verification and itsdangerous-based
signed session tokens for cookie authentication.
"""

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def hash_password(plain_password: str) -> bytes:
    """Hash a plaintext password using bcrypt.

    Raises ValueError if password is empty or exceeds 72 bytes (bcrypt limit).
    """
    if len(plain_password) == 0:
        raise ValueError("Password must not be empty")
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes (bcrypt limit)")
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())


def verify_password(plain_password: str, hashed_password: bytes) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Uses bcrypt.checkpw which is constant-time.
    Raises ValueError if plain_password is empty.
    """
    if len(plain_password) == 0:
        raise ValueError("Password must not be empty")
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password)


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


_token_service: AuthTokenService | None = None


def get_token_service() -> AuthTokenService:
    """Return the current AuthTokenService. Raises RuntimeError if not set."""
    if _token_service is None:
        raise RuntimeError(
            "AuthTokenService has not been set. Call set_token_service() first."
        )
    return _token_service


def set_token_service(service: AuthTokenService) -> None:
    """Set the global AuthTokenService instance."""
    global _token_service
    _token_service = service
