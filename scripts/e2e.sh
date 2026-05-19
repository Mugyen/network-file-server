#!/usr/bin/env bash
# Bring up a throwaway relay + open/restricted mounts and run the Playwright
# auth e2e suite against it. All state lives under a temp dir and is removed
# on exit (success or failure).
#
#   scripts/e2e.sh                 # full auth suite
#   scripts/e2e.sh --headed        # watch it in a browser
#   scripts/e2e.sh auth.spec.ts -g "signup"   # pass-through to playwright
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

HOST=127.0.0.1
PORT=8001
BASE_URL="http://${HOST}:${PORT}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/wfs-e2e.XXXXXX")"
RELAY_LOG="$WORK/relay.log"
OPEN_LOG="$WORK/open-mount.log"
REST_LOG="$WORK/restricted-mount.log"

RELAY_PID=""
OPEN_PID=""
REST_PID=""

cleanup() {
  set +e
  [ -n "$OPEN_PID" ] && kill "$OPEN_PID" 2>/dev/null
  [ -n "$REST_PID" ] && kill "$REST_PID" 2>/dev/null
  [ -n "$RELAY_PID" ] && kill "$RELAY_PID" 2>/dev/null
  wait 2>/dev/null
  rm -rf "$WORK"
}
trap cleanup EXIT

fail() { echo "e2e: $*" >&2; echo "--- relay.log ---" >&2; tail -n 40 "$RELAY_LOG" 2>/dev/null >&2; exit 1; }

# Unbuffered stdout: the agent prints the assigned mount "Code:" line we
# grep for; Python block-buffers stdout when it is a pipe, so without this
# the code never reaches the log and registration appears to hang.
export PYTHONUNBUFFERED=1

# --- Relay accounts env ---
export RELAY_SESSION_SECRET="e2e-$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')"
export RELAY_ADMIN_USERS="admin"
export RELAY_DB_PATH="$WORK/mounts.db"
export RELAY_ACCOUNTS_DB_PATH="$WORK/accounts.db"
# Keep the per-IP auth limiter out of the way of the seeding/login storm.
export RELAY_AUTH_SIGNUP_RATE="100000/hour"
export RELAY_AUTH_LOGIN_RATE="100000/minute"
export RELAY_AUTH_AGENT_TOKEN_RATE="100000/minute"

echo "e2e: building client bundle (relay serves it)"
(cd client && npm run build >/dev/null 2>&1) || fail "client build failed"

echo "e2e: starting relay on ${BASE_URL}"
uv run network-relay --host "$HOST" --port "$PORT" >"$RELAY_LOG" 2>&1 &
RELAY_PID=$!

for _ in $(seq 1 50); do
  if curl -fsS "${BASE_URL}/health" >/dev/null 2>&1; then break; fi
  kill -0 "$RELAY_PID" 2>/dev/null || fail "relay process exited during startup"
  sleep 0.3
done
curl -fsS "${BASE_URL}/health" >/dev/null 2>&1 || fail "relay /health never came up"

signup() {
  local u="$1" p="$2"
  curl -fsS -X POST "${BASE_URL}/auth/signup" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"${u}\",\"password\":\"${p}\"}" >/dev/null \
    || fail "signup failed for ${u}"
}
echo "e2e: seeding accounts (admin, alice, bob)"
signup admin pw-admin-1
signup alice pw-alice-1
signup bob pw-bob-1

# --- Mount folders with known files ---
OPEN_DIR="$WORK/open"; REST_DIR="$WORK/restricted"
mkdir -p "$OPEN_DIR" "$REST_DIR"
printf 'open mount payload\n' > "$OPEN_DIR/hello-open.txt"
printf 'top secret\n' > "$REST_DIR/secret-restricted.txt"

# Wait for "Code:       XXXXXXXX" in an agent log; echo the captured code.
capture_code() {
  local log="$1" pid="$2" code=""
  for _ in $(seq 1 60); do
    code="$(grep -oE '^Code:[[:space:]]+([^[:space:]]+)' "$log" 2>/dev/null | awk '{print $2}' | head -n1)"
    [ -n "$code" ] && { echo "$code"; return 0; }
    kill -0 "$pid" 2>/dev/null || return 1
    sleep 0.5
  done
  return 1
}

echo "e2e: mounting open folder"
uv run network-file-server mount "$OPEN_DIR" --server "$BASE_URL" \
  --name e2e-open --access-mode open >"$OPEN_LOG" 2>&1 &
OPEN_PID=$!
OPEN_CODE="$(capture_code "$OPEN_LOG" "$OPEN_PID")" || { cat "$OPEN_LOG" >&2; fail "open mount never registered"; }

echo "e2e: mounting restricted folder (owner=alice, no allowlist)"
printf 'pw-alice-1\n' | uv run network-file-server mount "$REST_DIR" --server "$BASE_URL" \
  --name e2e-restricted --login alice --access-mode restricted --password-stdin \
  >"$REST_LOG" 2>&1 &
REST_PID=$!
RESTRICTED_CODE="$(capture_code "$REST_LOG" "$REST_PID")" || { cat "$REST_LOG" >&2; fail "restricted mount never registered"; }

echo "e2e: open=${OPEN_CODE} restricted=${RESTRICTED_CODE}"

export E2E_BASE_URL="$BASE_URL"
export E2E_OPEN_CODE="$OPEN_CODE"
export E2E_RESTRICTED_CODE="$RESTRICTED_CODE"

echo "e2e: running Playwright"
(cd client && npx playwright test "$@")
