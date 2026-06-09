#!/usr/bin/env bash
# Run the test suite. Pass extra args/paths through to pytest.
#   scripts/test.sh                 # full suite + lint + type-check (+ client units if node_modules present)
#   scripts/test.sh tests/accounts  # a subset (pytest only)
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --group dev

if [ "$#" -eq 0 ]; then
  uv run ruff check .
  uv run mypy
fi

uv run --group dev python -m pytest "${@:-}" -q

# Client lint + unit tests — only on a full run, and only if deps are
# installed (scripts/install_setup.sh installs them).
if [ "$#" -eq 0 ] && [ -d client/node_modules ]; then
  (cd client && npm run lint)
  (cd client && npm run test:unit)
fi
