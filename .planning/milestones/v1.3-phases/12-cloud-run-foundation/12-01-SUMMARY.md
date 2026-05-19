---
phase: 12-cloud-run-foundation
plan: 01
subsystem: infra
tags: [docker, cloud-run, logging, health-check, fastapi]

# Dependency graph
requires:
  - phase: 09-relay-server
    provides: relay app factory, mount registry, CLI entry point
provides:
  - Multi-stage Dockerfile for relay containerization
  - GET /health endpoint with mount count
  - CloudJsonFormatter for Cloud Logging JSON output
  - RelayEnv enum for dev/production mode switching
  - deploy_relay.sh Cloud Run deployment script
  - Structured request and agent lifecycle logging
affects: [13-abuse-prevention, 14-persistent-mount-registry, 15-ux-polish-and-drop-box]

# Tech tracking
tech-stack:
  added: []
  patterns: [structured-json-logging, cloud-run-containerization, multi-stage-docker-build]

key-files:
  created:
    - relay/app/logging.py
    - relay/app/routers/health.py
    - Dockerfile
    - .dockerignore
    - deploy_relay.sh
    - tests/relay/test_health.py
    - tests/relay/test_logging.py
  modified:
    - relay/cli.py
    - relay/app/main.py
    - relay/app/routers/agent_ws.py
    - relay/app/routers/mount_proxy.py

key-decisions:
  - "Used --legacy-peer-deps for npm ci in Dockerfile to work around pre-existing vitest peer dependency conflict"
  - "README.md must be included in Docker context (not excluded by .dockerignore) because hatchling requires it for wheel build"

patterns-established:
  - "RelayEnv enum: use RelayEnv(str, Enum) for dev/production mode detection across relay modules"
  - "configure_logging(): call before uvicorn.run() to set up structured logging and suppress uvicorn access logs"
  - "App-level request logging: log in route handlers instead of uvicorn access log for structured fields"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03]

# Metrics
duration: 7min
completed: 2026-03-16
---

# Phase 12 Plan 01: Dockerfile, Health Endpoint, and Structured Logging Summary

**Multi-stage Docker build with Cloud Logging JSON formatter, /health liveness probe, and structured request/agent logging**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-16T17:34:29Z
- **Completed:** 2026-03-16T17:41:52Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- Multi-stage Dockerfile builds relay container (node:20-slim + python:3.11-slim + slim runtime)
- GET /health returns 200 with mount count for Cloud Run liveness probes
- CloudJsonFormatter emits JSON with severity field for Cloud Logging
- configure_logging(RelayEnv) switches between JSON (production) and text (development) output
- CLI reads PORT and RELAY_ENV env vars, passes proxy_headers=True to uvicorn
- Agent connect/disconnect and proxy request events logged with structured fields
- deploy_relay.sh deploys to Cloud Run with session-affinity and max-instances=1

## Task Commits

Each task was committed atomically:

1. **Task 1: Health endpoint and structured logging module (RED)** - `1c75755` (test)
2. **Task 1: Health endpoint and structured logging module (GREEN)** - `fd787f7` (feat)
3. **Task 2: CLI update, request logging, Dockerfile, and deploy script** - `01ac4dc` (feat)

_Note: Task 1 followed TDD (test -> feat). No refactor step needed._

## Files Created/Modified
- `relay/app/logging.py` - CloudJsonFormatter, RelayEnv enum, configure_logging()
- `relay/app/routers/health.py` - GET /health endpoint returning mount count
- `Dockerfile` - Multi-stage build: node -> python -> slim runtime
- `.dockerignore` - Excludes .git, .planning, tests, docs, __pycache__
- `deploy_relay.sh` - gcloud builds submit + gcloud run deploy script
- `relay/cli.py` - Reads PORT/RELAY_ENV env vars, configures logging, proxy_headers=True
- `relay/app/main.py` - Added health router to app factory
- `relay/app/routers/agent_ws.py` - Agent connect/disconnect logging
- `relay/app/routers/mount_proxy.py` - Request logging with method, path, status, duration, client IP
- `tests/relay/test_health.py` - 2 tests for health endpoint
- `tests/relay/test_logging.py` - 8 tests for JSON formatter, severity mapping, dev/prod modes

## Decisions Made
- Used `--legacy-peer-deps` for npm ci in Dockerfile to handle pre-existing vitest peer dependency conflict (devDependency version mismatch, does not affect production build)
- Added `!README.md` exception to .dockerignore because hatchling requires README.md for wheel build metadata

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] README.md excluded by .dockerignore breaks hatchling wheel build**
- **Found during:** Task 2 (Dockerfile creation)
- **Issue:** .dockerignore excluded `*.md`, but hatchling requires README.md (referenced in pyproject.toml) to build the wheel
- **Fix:** Added `!README.md` to .dockerignore and `README.md` to the COPY line in python-builder stage
- **Files modified:** .dockerignore, Dockerfile
- **Verification:** `docker build -t relay-test .` succeeds
- **Committed in:** 01ac4dc (Task 2 commit)

**2. [Rule 3 - Blocking] npm ci fails due to vitest peer dependency conflict**
- **Found during:** Task 2 (Dockerfile creation)
- **Issue:** `@vitest/coverage-v8@4.0.18` requires `vitest@4.0.18` but lockfile has `vitest@3.2.4` -- pre-existing issue in package.json
- **Fix:** Changed `npm ci --silent` to `npm ci --legacy-peer-deps` in Dockerfile (dev-only dependency, does not affect production build output)
- **Files modified:** Dockerfile
- **Verification:** `docker build -t relay-test .` succeeds, client/dist produced correctly
- **Committed in:** 01ac4dc (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes necessary for Docker build to succeed. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Relay container builds and runs successfully on Docker
- Health endpoint available for Cloud Run liveness probes
- Structured JSON logging ready for Cloud Logging
- CORS lockdown and HTTPS cookie fixes (plan 12-02) can build on this foundation
- deploy_relay.sh ready to use once GCP_PROJECT_ID and RELAY_ALLOWED_ORIGINS are set

## Self-Check: PASSED

All 7 created files verified present. All 3 task commits verified in git log.

---
*Phase: 12-cloud-run-foundation*
*Completed: 2026-03-16*
