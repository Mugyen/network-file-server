#!/usr/bin/env bash
# Install all dependencies (Python via uv, client via npm).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing Python deps (uv)..."
uv sync --group dev

echo "Installing client deps (npm)..."
(cd client && npm install --legacy-peer-deps)

echo "Done. See README.md for the accounts env vars (RELAY_SESSION_SECRET,"
echo "RELAY_ADMIN_USERS, RELAY_ACCOUNTS_DB_PATH, RELAY_DEFAULT_USER_QUOTA_BYTES)."
