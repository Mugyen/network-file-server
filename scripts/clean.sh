#!/usr/bin/env bash
# Delete regenerable artifacts (client build, caches, local SQLite DBs).
# Everything removed here is restored by install_setup.sh / build.sh / runtime.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf client/dist client/node_modules/.vite
# Playwright e2e outputs (browsers are a global cache, restored by install_setup.sh).
rm -rf client/test-results client/playwright-report client/.last-run.json
find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf .pytest_cache
# Local dev SQLite DBs (relay mount registry + accounts) — NOT production data.
rm -f /tmp/mounts.db /tmp/accounts.db
echo "Cleaned. Run scripts/install_setup.sh then scripts/build.sh to restore."
