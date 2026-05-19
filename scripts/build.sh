#!/usr/bin/env bash
# Build the client bundle (type-checks + Vite build). Python needs no build.
set -euo pipefail
cd "$(dirname "$0")/.."

(cd client && npm run build)
echo "Client built to client/dist/."
