"""Share link service for creating, validating, revoking, and listing share links.

Uses itsdangerous URLSafeTimedSerializer with a dedicated salt to produce
signed tokens that embed the shared file path and expire after a chosen TTL.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from server.app.models.enums import ShareTTL


@dataclass(frozen=True)
class ShareLinkRecord:
    """In-memory record of an active share link."""

    token: str
    file_path: str
    created_at: datetime
    ttl_seconds: int


class ShareLinkRevokedError(Exception):
    """Raised when a share link token has been revoked."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link has been revoked: {token}")


class ShareLinkNotFoundError(Exception):
    """Raised when a share link token is not found in the registry."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link not found: {token}")


class ShareLinkExpiredError(Exception):
    """Raised when a share link token has expired."""

    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(f"Share link has expired: {token}")


class ShareLinkService:
    """Creates, validates, revokes, and lists expiring share links.

    Tokens are signed with itsdangerous using a dedicated salt separate
    from auth session tokens. Active links are stored in-memory.
    """

    SALT = "share-link"

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key)
        self._active_links: dict[str, ShareLinkRecord] = {}

    def create_link(self, file_path: str, ttl: ShareTTL) -> str:
        """Create a new share link token for the given file path.

        Returns the signed token string. Registers the link in the active registry.
        """
        token: str = self._serializer.dumps({"path": file_path}, salt=self.SALT)
        now = datetime.now(tz=timezone.utc)
        record = ShareLinkRecord(
            token=token,
            file_path=file_path,
            created_at=now,
            ttl_seconds=int(ttl),
        )
        self._active_links[token] = record
        return token

    def validate_token(self, token: str) -> str:
        """Validate a share link token and return the embedded file path.

        Raises ShareLinkRevokedError if the token was revoked.
        Raises ShareLinkExpiredError if the token has expired.
        Raises BadSignature if the token is tampered or invalid.
        """
        if token not in self._active_links:
            raise ShareLinkRevokedError(token)

        record = self._active_links[token]
        try:
            data: dict[str, str] = self._serializer.loads(
                token, salt=self.SALT, max_age=record.ttl_seconds
            )
        except SignatureExpired:
            # Clean up expired entry
            del self._active_links[token]
            raise ShareLinkExpiredError(token)

        return data["path"]

    def revoke_link(self, token: str) -> None:
        """Revoke a share link by removing it from the active registry.

        Raises ShareLinkNotFoundError if the token is not in the registry.
        """
        if token not in self._active_links:
            raise ShareLinkNotFoundError(token)
        del self._active_links[token]

    def list_active_links(self) -> list[ShareLinkRecord]:
        """Return all non-expired active share links.

        Filters out naturally expired entries during listing.
        """
        active: list[ShareLinkRecord] = []
        expired_tokens: list[str] = []

        for token, record in self._active_links.items():
            try:
                self._serializer.loads(
                    token, salt=self.SALT, max_age=record.ttl_seconds
                )
                active.append(record)
            except SignatureExpired:
                expired_tokens.append(token)
            except BadSignature:
                expired_tokens.append(token)

        for token in expired_tokens:
            del self._active_links[token]

        return active


_share_service: ShareLinkService | None = None


def get_share_service() -> ShareLinkService:
    """Return the current ShareLinkService. Raises RuntimeError if not set."""
    if _share_service is None:
        raise RuntimeError(
            "ShareLinkService has not been set. Call set_share_service() first."
        )
    return _share_service


def set_share_service(service: ShareLinkService) -> None:
    """Set the global ShareLinkService instance."""
    global _share_service
    _share_service = service
