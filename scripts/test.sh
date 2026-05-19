#!/usr/bin/env bash
# Run the test suite. Pass extra args/paths through to pytest.
#   scripts/test.sh                 # full suite
#   scripts/test.sh tests/accounts  # a subset
set -euo pipefail
cd "$(dirname "$0")/.."

uv run --group dev python -m pytest "${@:-}" -q
