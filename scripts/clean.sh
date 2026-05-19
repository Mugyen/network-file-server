#!/usr/bin/env bash
# Delete regenerable artifacts (client build, caches, local SQLite DBs).
# Everything removed here is restored by install_setup.sh / build.sh / runtime.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf client/dist client/node_modules/.vite
find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache
# Local dev SQLite DBs (relay mount registry + accounts) — NOT production data.
rm -f /tmp/mounts.db /tmp/accounts.db
echo "Cleaned. Run scripts/install_setup.sh then scripts/build.sh to restore."
