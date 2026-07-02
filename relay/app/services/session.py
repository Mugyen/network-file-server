"""Relay session signing — itsdangerous-backed signed identity cookies.

This is web-layer glue (the accounts library is framework-agnostic and
contains no cookie/session code). Two token kinds share one secret via
distinct salts:

- session token: long-lived browser identity (cookie ``wfs_session``).
- agent-owner token: short-lived, proves an agent acts for an account
  during the mount registration handshake (Phase 4).
"""

import logging
from dataclasses import dataclass

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from relay.app.exceptions import InvalidSessionError

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "wfs_session"
SESSION_COOKIE_PATH = "/"
# Server-side validity of a session token (browser cookie itself is a
# session cookie). One week balances convenience vs. revocation latency.
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600

_SESSION_SALT = "wfs-relay-session"
_AGENT_SALT = "wfs-agent-owner"
_OIDC_STATE_SALT = "wfs-oidc-state"
# Owner tokens are exchanged immediately during the agent handshake, so a
# tight window limits replay if the wss connection is somehow captured.
AGENT_TOKEN_MAX_AGE_SECONDS = 120
# An OIDC round-trip (redirect to the IdP, sign in, come back) must complete
# within this window; also bounds how long a signed `state` is replayable.
OIDC_STATE_MAX_AGE_SECONDS = 600


@dataclass(frozen=True)
class SessionIdentity:
    """The authenticated identity carried by a valid session token."""

    user_id: int
    username: str


class RelaySession:
    """Issues and verifies signed session / agent-owner tokens."""

    def __init__(self, secret_key: str) -> None:
        if not isinstance(secret_key, str) or len(secret_key) == 0:
            raise ValueError("secret_key must be a non-empty string")
        self._session = URLSafeTimedSerializer(secret_key, salt=_SESSION_SALT)
        self._agent = URLSafeTimedSerializer(secret_key, salt=_AGENT_SALT)
        self._oidc_state = URLSafeTimedSerializer(secret_key, salt=_OIDC_STATE_SALT)

    # --- Browser session ------------------------------------------------

    def issue(self, user_id: int, username: str) -> str:
        """Create a signed session token for a logged-in user."""
        if not isinstance(user_id, int):
            raise TypeError("user_id must be an int")
        if not isinstance(username, str) or len(username) == 0:
            raise ValueError("username must be a non-empty string")
        return self._session.dumps({"uid": user_id, "username": username})

    def verify(self, token: str, max_age_seconds: int) -> SessionIdentity:
        """Validate a session token.

        Raises:
            InvalidSessionError: token is empty, tampered, or expired.
        """
        data = _loads_or_raise(self._session, token, max_age_seconds)
        return _to_identity(data)

    def verify_session_cookie(self, token: str) -> SessionIdentity:
        """verify() with the standard session max-age hard-coded.

        Used on every authenticated request, so the common max-age is
        fixed here rather than threaded through every call site.
        """
        return self.verify(token, SESSION_MAX_AGE_SECONDS)

    # --- OIDC login `state` (stateless CSRF round-trip) -----------------

    def issue_oauth_state(self, next_url: str, csrf: str) -> str:
        """Sign the OIDC `state`: the post-login redirect + a CSRF nonce.

        The nonce is also set as a short-lived cookie; the callback requires
        the two to match, binding the round-trip to this browser.
        """
        if not isinstance(next_url, str):
            raise TypeError("next_url must be a str")
        if not isinstance(csrf, str) or len(csrf) == 0:
            raise ValueError("csrf must be a non-empty string")
        return self._oidc_state.dumps({"next": next_url, "csrf": csrf})

    def verify_oauth_state(self, token: str) -> tuple[str, str]:
        """Return (next_url, csrf) from a valid state token.

        Raises:
            InvalidSessionError: token empty, tampered, expired, or malformed.
        """
        data = _loads_or_raise(self._oidc_state, token, OIDC_STATE_MAX_AGE_SECONDS)
        try:
            return str(data["next"]), str(data["csrf"])
        except (KeyError, TypeError) as exc:
            raise InvalidSessionError("malformed oidc state") from exc

    # --- Agent-owner token (Phase 4) ------------------------------------

    def issue_agent_owner_token(self, user_id: int) -> str:
        """Create a short-lived token proving an agent acts for a user."""
        if not isinstance(user_id, int):
            raise TypeError("user_id must be an int")
        return self._agent.dumps({"uid": user_id, "purpose": "agent"})

    def verify_agent_owner_token(self, token: str) -> int:
        """Return the owner user_id from a valid agent token.

        Raises:
            InvalidSessionError: token is empty, tampered, expired, or not
                an agent-purpose token.
        """
        data = _loads_or_raise(self._agent, token, AGENT_TOKEN_MAX_AGE_SECONDS)
        if data.get("purpose") != "agent":
            raise InvalidSessionError("not an agent-owner token")
        try:
            return int(data["uid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidSessionError("malformed agent token payload") from exc


def _loads_or_raise(
    serializer: URLSafeTimedSerializer, token: str, max_age_seconds: int
) -> dict:
    if not isinstance(token, str) or len(token) == 0:
        raise InvalidSessionError("empty token")
    try:
        return serializer.loads(token, max_age=max_age_seconds)
    except SignatureExpired as exc:
        raise InvalidSessionError("token expired") from exc
    except BadSignature as exc:
        raise InvalidSessionError("invalid signature") from exc


def _to_identity(data: dict) -> SessionIdentity:
    try:
        return SessionIdentity(
            user_id=int(data["uid"]),
            username=str(data["username"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidSessionError("malformed session payload") from exc
