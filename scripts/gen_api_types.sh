#!/usr/bin/env bash
# Regenerate client/src/types/api.gen.ts from the server's OpenAPI schema.
#
# The server is the single source of truth for API request/response shapes.
# This dumps its OpenAPI schema and runs openapi-typescript over it. CI runs
# the same command and `git diff --exit-code`s the result, so a backend
# schema change that is not regenerated here fails the build.
#
# Usage: ./scripts/gen_api_types.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="client/src/types/api.gen.ts"
SCHEMA="$(mktemp)"
trap 'rm -f "$SCHEMA"' EXIT

echo "Dumping OpenAPI schema..."
uv run python -m server.app.openapi_dump > "$SCHEMA"

echo "Generating $OUT ..."
( cd client && npx --no-install openapi-typescript "$SCHEMA" -o "src/types/api.gen.ts" )

echo "Done. $OUT regenerated."
