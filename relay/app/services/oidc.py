"""Minimal OIDC (OpenID Connect) client for the relay's optional SSO login.

Web-layer glue for a *confidential* authorization-code client. The relay is
its own OIDC client of the identity broker (Authentik); this runs the code
flow and returns the caller's canonical claims.

Why this is httpx-only (no JWT library): the authorization code is exchanged,
and userinfo fetched, over a **direct server-to-server TLS** connection to the
issuer — a channel already authenticated by TLS and the client secret. We read
the canonical identity from the ``userinfo`` endpoint rather than parsing/
verifying the ``id_token`` ourselves. CSRF and request-binding are handled by a
signed ``state`` + a matching short-lived cookie in the router. The canonical
subject is the opaque OIDC ``sub`` (a UUID) — never the email.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(10.0)


class OidcError(Exception):
    """Any failure talking to the identity provider (discovery/token/userinfo)."""


@dataclass
class OidcClient:
    """A confidential OIDC code-flow client bound to one provider.

    ``issuer`` is the provider's issuer URL (per-provider for Authentik). The
    OIDC endpoints are discovered from ``<issuer>/.well-known/openid-configuration``
    and cached for the process lifetime.
    """

    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str = "openid profile email"
    _discovery: dict | None = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def _discover(self) -> dict:
        if self._discovery is not None:
            return self._discovery
        async with self._lock:
            if self._discovery is not None:  # double-checked under lock
                return self._discovery
            url = self.issuer.rstrip("/") + "/.well-known/openid-configuration"
            try:
                async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    self._discovery = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OidcError(f"OIDC discovery failed: {exc}") from exc
            return self._discovery

    async def authorize_url(self, state: str) -> str:
        """Build the provider authorize URL to redirect the browser to."""
        disc = await self._discover()
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": self.scopes,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{disc['authorization_endpoint']}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for tokens (client_secret_post)."""
        disc = await self._discover()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.post(disc["token_endpoint"], data=data)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OidcError(f"token exchange failed: {exc}") from exc

    async def fetch_userinfo(self, access_token: str) -> dict:
        """Fetch the caller's claims from the userinfo endpoint.

        Returns the raw claim dict — callers read ``sub`` (canonical UUID),
        ``email``, ``preferred_username``, ``name``, ``groups``.
        """
        disc = await self._discover()
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                resp = await client.get(
                    disc["userinfo_endpoint"],
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OidcError(f"userinfo fetch failed: {exc}") from exc
