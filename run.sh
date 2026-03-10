#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

# Build frontend
npm --prefix client run build --silent

# Start server, forwarding all arguments
uv run python -m server.app.cli "$@"
