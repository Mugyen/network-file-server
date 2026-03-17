#!/usr/bin/env bash
# Mount a local folder through the relay (rebuilds client if source is newer than dist).
# Usage: ./run_mount_server.sh /path/to/folder --relay http://host:port [extra args...]
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "Usage: $0 /path/to/folder --relay http://host:port [--password PW] [--ttl 30m]"
  exit 1
fi

# Rebuild client if dist is stale or missing
if [ ! -d client/dist ] || [ "$(find client/src -newer client/dist -print -quit 2>/dev/null)" ]; then
  echo "Building client..."
  (cd client && npm install --legacy-peer-deps --silent && npm run build)
fi

FOLDER="$1"
shift

# Translate --relay to --server for the underlying CLI
ARGS=()
HAS_SERVER=false
for arg in "$@"; do
  if [ "$arg" = "--relay" ]; then
    ARGS+=("--server")
    HAS_SERVER=true
  else
    ARGS+=("$arg")
  fi
done

if [ "$HAS_SERVER" = true ]; then
  echo "Mounting $FOLDER through relay..."
  exec uv run network-file-server mount "$FOLDER" "${ARGS[@]}"
else
  echo "Serving $FOLDER on LAN..."
  exec uv run network-file-server "$FOLDER" "${ARGS[@]}"
fi
