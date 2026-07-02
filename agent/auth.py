"""Agent owner authentication.

When a mount is started with ``--login``, the agent exchanges the owner's
relay credentials for a short-lived owner token over HTTPS. That token is
sent in the ``agent_auth`` control message during the mount registration
handshake so the relay can bind the mount to the owning account and apply
its access policy.
"""

from dataclasses import dataclass

import httpx

from accounts import AccessMode, Role, SubjectType
from agent.exceptions import AgentAuthError


@dataclass(frozen=True)
class AgentAllowEntry:
    """One declared allowlist entry (resolved to ids by the relay)."""

    subject_type: SubjectType
    subject_ref: str
    role: Role


@dataclass(frozen=True)
class AgentOwner:
    """Owner identity + declared access policy for a mount."""

    username: str
    password: str
    access_mode: AccessMode
    allowlist: tuple[AgentAllowEntry, ...]


def parse_allow_entry(spec: str) -> AgentAllowEntry:
    """Parse a ``--allow`` value ``type:ref:role`` into an AgentAllowEntry.

    The ``ref`` may itself contain ``:`` — identity-broker group names follow
    the ``app:<service>:<role>`` convention (e.g. ``app:files:eng``) — so the
    type is peeled off the front and the role off the back rather than a plain
    3-way split.

    Raises:
        ValueError: if the spec is malformed or uses unknown type/role.
    """
    type_str, sep_head, rest = spec.partition(":")
    ref, sep_tail, role_str = rest.rpartition(":")
    if not sep_head or not sep_tail:
        raise ValueError(
            f"--allow must be 'type:ref:role' (e.g. user:alice:write), got {spec!r}"
        )
    type_str, ref, role_str = type_str.strip(), ref.strip(), role_str.strip()
    if not ref:
        raise ValueError(f"--allow reference must be non-empty in {spec!r}")
    try:
        subject_type = SubjectType(type_str)
    except ValueError as exc:
        raise ValueError(
            f"--allow type must be 'user' or 'group', got {type_str!r}"
        ) from exc
    try:
        role = Role(role_str)
    except ValueError as exc:
        raise ValueError(
            f"--allow role must be read|write|receive, got {role_str!r}"
        ) from exc
    return AgentAllowEntry(subject_type=subject_type, subject_ref=ref, role=role)


async def fetch_agent_token(relay_url: str, username: str, password: str) -> str:
    """Exchange owner credentials for a short-lived relay owner token.

    Raises:
        AgentAuthError: relay unreachable, credentials rejected, or a
            malformed response.
    """
    base = relay_url.rstrip("/")
    url = f"{base}/auth/agent-token"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, json={"username": username, "password": password}
            )
    except httpx.HTTPError as exc:
        raise AgentAuthError(
            f"Could not reach relay auth endpoint {url}: {exc}"
        ) from exc

    if resp.status_code == 401:
        raise AgentAuthError("Relay rejected owner credentials")
    if resp.status_code != 200:
        raise AgentAuthError(f"Relay auth failed: HTTP {resp.status_code}")

    data = resp.json()
    token = data.get("token")
    if not token:
        raise AgentAuthError("Relay auth response did not include a token")
    return token
