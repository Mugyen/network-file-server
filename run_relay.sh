#!/usr/bin/env bash
# Start the relay server (rebuilds client if source is newer than dist).
set -euo pipefail
cd "$(dirname "$0")"

# Rebuild client if dist is stale or missing
if [ ! -d client/dist ] || [ "$(find client/src -newer client/dist -print -quit 2>/dev/null)" ]; then
  echo "Building client..."
  (cd client && npm install --silent && npm run build)
fi

echo "Starting relay on 0.0.0.0:8001..."
exec uv run wifi-relay "$@"
