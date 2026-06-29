# Deployment: HTTPS everywhere, one codebase

The client and relay run in three contexts. The goal is that **every context
is a browser secure context**, so secure-context-only APIs
(`crypto.randomUUID`, `navigator.clipboard`, service workers, notifications)
work everywhere with no per-mode code. TLS always lives in a reverse proxy
(Caddy); the app itself only ever speaks plain HTTP.

| Context | URL | Secure context? | TLS by |
|---|---|---|---|
| Localhost dev | `http://localhost:*` | Yes (browser built-in) | — |
| Public VPS (relay) | `https://<host>` | Yes | Caddy + Let's Encrypt |
| LAN-direct server | `https://lan.<domain>` (planned) | Yes | Caddy + DNS-01 cert |
| LAN fallback / raw IP | `http://192.168.x.x` | **No** — fallbacks apply | — |

## Why this architecture

- **No TLS in app code.** uvicorn runs plain HTTP behind a proxy
  (`proxy_headers=True`, `forwarded_allow_ips="*"` in `relay/cli.py`;
  `SecureCookieMiddleware` already honors `X-Forwarded-Proto`). Certs,
  renewal, and HTTP→HTTPS redirects are Caddy's job.
- **Same client bundle in every mode.** The client derives `ws:`/`wss:` from
  `window.location.protocol` (`client/src/utils/remoteMount.ts`); the agent
  converts `https://` → `wss://` (`agent/connection.py`). Nothing is
  mode-switched.
- **Secure-context fallbacks stay** (see policy below) as a safety net for
  raw-IP HTTP access.

## Relay on a GCP VM (current production setup)

State as of 2026-06-17: relay served at `https://agents.mugyen.com`
(real domain; DNS A record → VM external IP `34.30.19.224`), VM
`agent-sandbox`, zone `us-central1-c`.

Layers, outermost first:

1. **GCP firewall** — only 80/443 open (standard `http-server`/`https-server`
   tags). The relay port (8001) is NOT exposed; the relay additionally binds
   `127.0.0.1` so even a stray firewall rule exposes nothing.
2. **Caddy** (`/etc/caddy/Caddyfile`) — TLS termination, automatic Let's
   Encrypt issuance/renewal, HTTP→HTTPS 308 redirect, transparent WebSocket
   proxying:

   ```
   agents.mugyen.com {
       reverse_proxy localhost:8001
       header Strict-Transport-Security "max-age=31536000; includeSubDomains"
   }
   ```

3. **systemd** (`/etc/systemd/system/network-relay.service`) — runs
   `scripts/run.sh relay --host 127.0.0.1` as the login user.
   `run.sh` makes restart a full deploy: it re-syncs Python deps (`uv run`)
   and rebuilds `client/dist` when `client/src` is newer. `StartLimitBurst`
   stops a broken client build from restart-looping npm. `uv` and node (nvm)
   are user-local, so the unit carries an explicit `Environment=PATH=…`.
4. **Relay env** (`<repo>/.relay.env`, `chmod 600`) — production mode:

   ```bash
   RELAY_ENV=production                              # JSON logs; strict CORS
   RELAY_ALLOWED_ORIGINS=https://agents.mugyen.com   # must match Caddy host
   RELAY_PUBLIC_URL=https://agents.mugyen.com        # how the relay names itself (drop box QR); defaults to first allowed origin
   PORT=8001
   RELAY_DB_PATH=$HOME/relay-data/mounts.db          # NOT /tmp — survives reboot
   RELAY_DATA_DIR=$HOME/relay-data/data
   RELAY_SESSION_SECRET=<stable random>              # sessions survive restarts
   ```

Deploying a change: `git pull && sudo systemctl restart network-relay`.

Agents mount with the HTTPS origin:

```bash
uv run network-file-server /folder mount --relay https://agents.mugyen.com
```

### Verification checklist (all confirmed 2026-06-11)

- `curl https://<host>/health` → `{"status": "ok", ...}` with a trusted cert
- `curl -I http://<host>/` → `308` to HTTPS
- Browser WS `wss://<host>/m/<code>/ws` and agent WS `wss://<host>/agent/ws`
  upgrade with `101` through Caddy. **Test WS with `curl --http1.1`** — curl
  defaults to HTTP/2 on HTTPS, where Upgrade headers don't exist and you get
  a misleading 200/404; browsers and the Python `websockets` library use
  HTTP/1.1 for WS.
- `http://<external-ip>:8001/` from outside times out (localhost bind)

### Swapping in the real domain (done 2026-06-17)

The `nip.io` host was retired for `agents.mugyen.com`. The procedure, for
reference if the domain ever changes again:

1. DNS A record: `agents.mugyen.com` → VM external IP `34.30.19.224`.
2. Replace the host line in `/etc/caddy/Caddyfile`; `sudo systemctl reload caddy`
   (Caddy auto-issues the Let's Encrypt cert for the new host on first request).
3. Update `RELAY_ALLOWED_ORIGINS` and `RELAY_PUBLIC_URL` in `.relay.env`;
   `sudo systemctl restart network-relay`.
4. HSTS is enabled now that the host is a stable real domain (never on a
   host that must also serve plain HTTP):
   `header Strict-Transport-Security "max-age=31536000; includeSubDomains"`.

## LAN-direct server over HTTPS (planned, needs the domain)

Publicly-trusted certs can't be issued for private IPs, and HTTP-01
validation can't reach a LAN box. The **DNS-01 challenge** solves both —
ownership is proven by writing a DNS TXT record via the DNS provider's API,
so no inbound connectivity is needed:

1. Public DNS A record `lan.<domain>` → the LAN box's private IP
   (e.g. `192.168.1.5`; public DNS pointing at RFC1918 space is fine — it
   only resolves usefully on your LAN).
2. Caddy on the LAN box with a DNS provider module (Cloudflare is the usual
   choice; needs a Caddy build with the plugin, e.g. via `xcaddy` or the
   download page):

   ```
   lan.<domain> {
       reverse_proxy localhost:8000
       tls { dns cloudflare {env.CF_API_TOKEN} }
   }
   ```

3. Devices on the WiFi open `https://lan.<domain>` — trusted cert, full
   secure context, zero per-device setup (guests' phones included).

Scales by subdomain-per-site reusing the same DNS token, or one wildcard
cert. Rejected alternatives: mkcert/private CA (needs cert install on every
device), Tailscale certs (needs the app on every client), routing LAN
traffic through the public relay (loses local speed).

## Secure-context API policy (code review rule)

`localhost` and HTTPS are secure contexts; `http://<any-ip>` is not. Raw-IP
HTTP access remains supported, so **any use of a secure-context-only API
must feature-detect and degrade**:

- UUIDs: use `generateUuid()` (`client/src/types/websocket.ts`) — prefers
  `crypto.randomUUID`, falls back to `crypto.getRandomValues` (same CSPRNG,
  not gated).
- Clipboard: use `copyToClipboard()` (`client/src/utils/copyToClipboard.ts`)
  — prefers `navigator.clipboard`, falls back to textarea + `execCommand`.
- Service worker registration is feature-detected in `client/src/main.tsx`.
- New APIs without a fallback (notifications, etc.): gate the *feature*, not
  just the call — it should be invisible, not broken, on raw-IP HTTP.

The trap to watch for: localhost dev and HTTPS prod both work, so an
unguarded call only fails on raw-IP HTTP — usually on someone's phone, weeks
later. (This shipped twice: `crypto.randomUUID` in `getDeviceId` white-
screened the whole app, and `ShareDialog`'s copy button silently no-opped.
Both fixed 2026-06-11.)
