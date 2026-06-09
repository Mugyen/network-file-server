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
