#!/usr/bin/env bash
# Run the project in one of its modes.
#
#   scripts/run.sh relay [args...]                 # start the relay
#   scripts/run.sh lan   <folder> [args...]        # serve a folder on the LAN
#   scripts/run.sh mount <folder> --server <url> \
#       [--login <user> --access-mode restricted --allow user:bob:write] [args...]
#
# Accounts env (relay): RELAY_SESSION_SECRET, RELAY_ADMIN_USERS,
# RELAY_ACCOUNTS_DB_PATH, RELAY_DEFAULT_USER_QUOTA_BYTES.
set -euo pipefail
cd "$(dirname "$0")/.."

mode="${1:-}"; shift || true

# Rebuild client if stale.
if [ ! -d client/dist ] || [ "$(find client/src -newer client/dist -print -quit 2>/dev/null)" ]; then
  (cd client && npm install --legacy-peer-deps --silent && npm run build)
fi

case "$mode" in
  relay) exec uv run network-relay "$@" ;;
  lan)   exec uv run network-file-server "$@" ;;
  mount) exec uv run network-file-server mount "$@" ;;
  *) echo "Usage: scripts/run.sh {relay|lan|mount} [args...]" >&2; exit 1 ;;
esac
