# Network File Server

Share files over your local network. Any device on the same network can browse and download files via a web browser.

## Setup

```bash
uv sync
```

## Run

```bash
uv run network-file-server /path/to/folder
uv run network-file-server /path/to/folder --port 9000
uv run network-file-server /path/to/folder --host 127.0.0.1 --port 9000
```

Scan the QR code printed in the terminal from any device on the same network.

## Relay (remote access)

Start the relay server to expose mounts outside your LAN:

```bash
uv run network-relay              # binds 0.0.0.0:8001
uv run network-relay --port 9001  # custom port
uv run network-relay --host 127.0.0.1  # localhost only
```

Mount a local folder through the relay from any machine:

```bash
uv run network-file-server /path/to/folder mount --relay http://relay-host:8001
```

## User accounts (relay)

The relay is the identity provider for all its mounts (GitHub-Enterprise
style). Accounts + groups live in a SQLite DB on the relay.

Relay env:

```bash
RELAY_SESSION_SECRET=<stable-random>      # required in prod; ephemeral if unset
RELAY_ADMIN_USERS=alice,bob               # comma-separated admin usernames
RELAY_ACCOUNTS_DB_PATH=/data/accounts.db  # default: sibling of RELAY_DB_PATH
RELAY_DEFAULT_USER_QUOTA_BYTES=1073741824 # per-user relay storage (1 GiB)
```

- Visitors self-register at `/signup` (unique username + password), sign in
  at `/login`, or **continue as guest** for open mounts.
- Admins (from `RELAY_ADMIN_USERS`) manage users/groups and approve access
  requests at `/admin`. Groups may contain users *and* other groups.
- Per-user relay storage: `GET/POST/DELETE /me/files`, `GET /me/quota`
  (login required; 413 over quota).

Mount with account access control (the per-mount `--password` still works
and is an independent fallback — signing in as an allowlisted user bypasses
it; not being allowlisted falls back to it):

```bash
uv run network-file-server mount /folder --server https://relay \
  --login alice --access-mode restricted \
  --allow user:bob:write --allow group:eng:read
# password via prompt, or: echo "$PW" | ... --password-stdin
```

Roles: `read` (browse/download), `write` (full), `receive` (upload + see
only your own uploads). Restricted mounts with **no** password require an
allowlisted login; non-allowlisted users can submit an access request that
the mount owner or an admin approves. **LAN-direct** access (no relay) is
unaffected and still guarded only by the per-mount password.

## Optional SSO (OIDC)

The relay can *additionally* offer "Sign in with Mugyen" (an OIDC login against
an identity broker such as Authentik) **alongside** anonymous access and local
password accounts — nothing existing changes. It's a confidential
authorization-code client; enable it by setting all three credentials:

```bash
RELAY_OIDC_ISSUER=https://auth.apps.mugyen.com/application/o/files/
RELAY_OIDC_CLIENT_ID=<client id>
RELAY_OIDC_CLIENT_SECRET=<client secret>     # keep in .relay.env (gitignored)
# optional:
RELAY_OIDC_REDIRECT_PATH=/auth/oidc/callback # default; register this at the IdP
RELAY_OIDC_SCOPES="openid profile email"     # default
RELAY_OIDC_GROUP_PREFIX=app:files:           # sync IdP groups with this prefix
```

- Redirect URI to register at the IdP is `${RELAY_PUBLIC_URL}${RELAY_OIDC_REDIRECT_PATH}`.
- SSO login (`GET /auth/oidc/login`) mints the **same** `wfs_session` cookie as
  password login, so all mount/storage/admin authorization works unchanged.
- Accounts are keyed on the IdP's opaque `sub` (a UUID) — never email; a new
  subject gets a **new** local account (no auto-merge with password accounts).
- With `RELAY_OIDC_GROUP_PREFIX` set, matching IdP groups (e.g. `app:files:eng`)
  are mirrored into local relay groups on login (additive; never revoked), so
  mount allowlists can grant access to them. Admin is still username-based
  (`RELAY_ADMIN_USERS`); an SSO account's generated username can be added there.
- Unset the credentials and the SSO route/button disappear — no other effect.

## Docker (Cloud Run)

```bash
docker build -t network-relay .
docker run -e PORT=8080 -p 8080:8080 network-relay
```

Deploy to Cloud Run:

```bash
GCP_PROJECT_ID=my-project RELAY_ALLOWED_ORIGINS=https://example.com ./deploy_relay.sh
```

Health check: `GET /health` returns `{"status": "ok", "mounts": 0}`.

Set `RELAY_ENV=production` for JSON logging (Cloud Logging compatible).

Set `RELAY_DB_PATH=/path/to/mounts.db` to override SQLite mount registry location (default: `/tmp/mounts.db`).

## GCP VM deployment (systemd)

Run the relay as a persistent service on a Compute Engine VM (alternative to
Cloud Run), with TLS terminated by Caddy in front of the plain-HTTP relay.
Full walkthrough incl. the HTTPS/secure-context rationale:
[docs/deployment.md](docs/deployment.md).

The service runs `scripts/run.sh relay --host 127.0.0.1`, which syncs Python
deps (via `uv run`) and rebuilds the client bundle when `client/src` is newer
than `client/dist` — so a `git pull` + `systemctl restart` is a full deploy.
The relay binds localhost only; Caddy is the sole public entrypoint.

Create an env file at the repo root (`.relay.env`, `chmod 600`) so data
survives reboots and sessions survive restarts:

```bash
RELAY_ENV=production
RELAY_ALLOWED_ORIGINS=https://<your-hostname>   # the public origin Caddy serves
PORT=8001
RELAY_DB_PATH=$HOME/relay-data/mounts.db
RELAY_DATA_DIR=$HOME/relay-data/data
RELAY_SESSION_SECRET=<openssl rand -base64 32>
```

Install the unit at `/etc/systemd/system/network-relay.service`:

```ini
[Unit]
Description=Network File Server relay
After=network-online.target
Wants=network-online.target
# Stop retrying if startup (incl. the client rebuild in run.sh) keeps failing
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
User=<user>
WorkingDirectory=<repo>
EnvironmentFile=<repo>/.relay.env
# uv and node are usually user-local installs, not on systemd's default PATH
Environment=PATH=<home>/.local/bin:<path-to-node-bin>:/usr/local/bin:/usr/bin:/bin
ExecStart=<repo>/scripts/run.sh relay --host 127.0.0.1
Restart=always
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=<home>/relay-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now network-relay
sudo journalctl -u network-relay -f   # logs
```

Put Caddy in front for HTTPS (`sudo apt install caddy`). It auto-issues and
renews Let's Encrypt certs and redirects HTTP→HTTPS. `/etc/caddy/Caddyfile`:

```
<your-hostname> {
    reverse_proxy localhost:8001
}
```

No domain yet? `<external-ip>.nip.io` (e.g. `34.30.19.224.nip.io`) resolves
to your IP and gets real Let's Encrypt certs. Swapping in a real domain later
is a one-line Caddyfile change + `RELAY_ALLOWED_ORIGINS` update.

Firewall: only 80/443 need to be open (the standard `http-server` /
`https-server` GCP tags). Do **not** expose the relay port itself.

Verify from outside: `curl https://<your-hostname>/health`.

## API

- `GET /api/files?path=` -- list directory contents
- `POST /api/files/upload?path=&conflict_resolution=` -- upload files (multipart)
- `GET /api/files/download?path=` -- download single file
- `POST /api/files/download-zip` -- download multiple files as ZIP (JSON body: `{"paths": [...]}`)
- `PATCH /api/files/rename` -- rename file/folder (JSON body: `{"path": "...", "new_name": "..."}`)
- `DELETE /api/files` -- delete files/folders (JSON body: `{"paths": [...]}`)
- `POST /api/folders` -- create folder (JSON body: `{"parent_path": "...", "name": "..."}`)
- `GET /api/server-info` -- server IP, port, URL, QR code (SVG), all LAN IPs

## Test

```bash
uv sync --group dev          # install pytest/ruff/mypy/pytest-asyncio for local runs
scripts/test.sh                 # full check: ruff + mypy + pytest + client lint + vitest
scripts/test.sh tests/accounts  # a pytest subset (skips lint/typecheck/client)
scripts/e2e.sh                  # Playwright e2e: auth + core flows (throwaway relay + mounts)
scripts/e2e.sh -g signup        # one e2e test (args pass through to playwright)
```

CI (`.github/workflows/ci.yml`) runs the same checks on push/PR; e2e via manual dispatch.

If you want to invoke pytest directly, run it through uv after syncing the dev group:

```bash
uv run --group dev python -m pytest
```

`scripts/e2e.sh` needs Playwright Chromium (`scripts/install_setup.sh` installs it).

Helper scripts: `scripts/{install_setup,build,run,test,e2e,clean}.sh`.

## Client Development

```bash
cd client && npm install && npm run dev
```

Vite proxies `/api` requests to `localhost:8000`. Run the backend in a separate terminal.

API response/request types are generated from the server's OpenAPI schema into
`client/src/types/api.gen.ts` (never edit by hand). After changing a backend
schema, regenerate and commit:

```bash
./scripts/gen_api_types.sh   # or: cd client && npm run gen:api
```

CI fails if the committed types drift from the live schema.

## Features

- Browse files and folders with double-click navigation and breadcrumbs
- Upload via drag-and-drop or toolbar button with progress tracking
- Download individual files or batch-download selected files as ZIP
- Select files with checkboxes, select all, batch delete with confirmation
- Rename files inline, create new folders
- Responsive layout -- mobile-friendly

## Requirements

- Python 3.11+
- uv
- Node.js 20+ (for client)
