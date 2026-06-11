"""HMAC signing for relay-injected identity headers.

The relay strips inbound ``X-WFS-*`` headers and injects authoritative ones
(user, role, auth-bypass) for allowlisted users. Without a signature, any
client that can reach the agent's local server port directly (e.g. on the
LAN, bypassing the tunnel) could forge those headers and assume an
allowlisted identity.

This module is the shared contract: the relay signs the identity tuple with
a per-mount secret (established by the agent at connect time and known to
both the relay and the agent's embedded server), and the server verifies the
signature before trusting any identity header. A forging client does not know
the secret, so its headers carry no valid signature and are ignored.

The secret is per-mount and per-agent-session: each mount has a distinct
secret, so a signature minted for one mount cannot be replayed against
another. Replay *within* a single mount requires capturing a legitimate
signed request, which means the attacker is already inside the agent's local
trust boundary — out of scope for this control.

Lives in ``shared`` because both ``relay`` (signer) and ``server`` (verifier)
must use byte-identical canonicalization; a leaf module keeps them in lockstep.
"""

import hashlib
import hmac

IDENTITY_SIG_HEADER = "x-wfs-identity-sig"


def _canonical(user: str, role: str, bypass: bool) -> bytes:
    """Canonical byte string signed/verified for an identity tuple.

    Newline-delimited so no field separator can appear inside a field
    (header values never contain newlines).
    """
    if not isinstance(user, str) or not isinstance(role, str):
        raise ValueError("user and role must be strings")
    return f"{user}\n{role}\n{1 if bypass else 0}".encode("utf-8")


def sign_identity(secret: str, user: str, role: str, bypass: bool) -> str:
    """Return the hex HMAC-SHA256 signature for an identity tuple.

    Raises:
        ValueError: If secret is not a non-empty string.
    """
    if not isinstance(secret, str) or len(secret) == 0:
        raise ValueError("secret must be a non-empty string")
    return hmac.new(
        secret.encode("utf-8"), _canonical(user, role, bypass), hashlib.sha256
    ).hexdigest()


def verify_identity(
    secret: str, user: str, role: str, bypass: bool, signature: str
) -> bool:
    """Constant-time check that ``signature`` matches the identity tuple.

    Returns False for an empty/typeless signature rather than raising — a
    missing signature is the expected "untrusted" case, not an error.

    Raises:
        ValueError: If secret is not a non-empty string.
    """
    if not isinstance(secret, str) or len(secret) == 0:
        raise ValueError("secret must be a non-empty string")
    if not isinstance(signature, str) or len(signature) == 0:
        return False
    expected = sign_identity(secret, user, role, bypass)
    return hmac.compare_digest(expected, signature)
