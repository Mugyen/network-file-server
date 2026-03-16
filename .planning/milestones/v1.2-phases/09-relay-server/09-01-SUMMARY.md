---
phase: 09-relay-server
plan: "01"
subsystem: relay
tags: [relay, mount-registry, fastapi, jinja2, tdd]
dependency_graph:
  requires: []
  provides:
    - relay package importable
    - MountRegistry with full mount lifecycle
    - Landing page router and Jinja2 templates
    - create_relay_app() factory
  affects:
    - relay/app/routers/ (landing router mounted)
    - pyproject.toml (relay added to build targets)
tech_stack:
  added:
    - relay/ package (new FastAPI application)
    - Jinja2Templates with light/dark CSS via prefers-color-scheme
  patterns:
    - MountStatus(str, Enum) following server/app/models/enums.py pattern
    - Typed exceptions with .code attribute following server/app/exceptions.py pattern
    - get_registry/set_registry module-level singleton for test injection
    - TDD: RED (failing tests) then GREEN (minimal implementation)
key_files:
  created:
    - relay/__init__.py
    - relay/app/__init__.py
    - relay/app/enums.py
    - relay/app/exceptions.py
    - relay/app/services/__init__.py
    - relay/app/services/mount_registry.py
    - relay/app/routers/__init__.py
    - relay/app/routers/landing.py
    - relay/app/main.py
    - relay/templates/base.html
    - relay/templates/landing.html
    - relay/templates/not_found.html
    - relay/templates/offline.html
    - relay/templates/expired.html
    - tests/relay/conftest.py
    - tests/relay/test_mount_registry.py
    - tests/relay/test_landing.py
  modified:
    - pyproject.toml (added relay to build targets)
    - docs/project-log.md
decisions:
  - "MountRegistry uses typed exceptions (MountNotFoundError/MountOfflineError/MountExpiredError) with .code attribute for HTTP response use in Plan 02"
  - "generate_mount_code uses secrets.token_urlsafe(6) which produces exactly 8 URL-safe base64 characters"
  - "tests/relay/ has no __init__.py to prevent sys.path shadowing of the real relay/ package (same pattern as tests/tunnel/)"
  - "landing router exports templates instance so mount_proxy.py (Plan 02) can reuse the same Jinja2Templates for error pages"
  - "Query('') used for code param — FastAPI dependency, not Python default param (compliant with project no-defaults rule)"
metrics:
  duration: "3m"
  completed_date: "2026-03-11"
  tasks_completed: 2
  files_created: 17
  tests_added: 33
---

# Phase 9 Plan 1: Relay Server Foundation Summary

Relay package with MountRegistry service, typed exception hierarchy, Jinja2 error templates, and landing router with code-based 302 redirect.

## What Was Built

### Task 1: Relay package foundation

- `relay/app/enums.py` — `MountStatus(str, Enum)` with ONLINE/OFFLINE/EXPIRED values
- `relay/app/exceptions.py` — `MountNotFoundError`, `MountOfflineError`, `MountExpiredError`, each storing `.code`
- `relay/app/services/mount_registry.py` — `MountRegistry` with `register`, `deregister`, `get_connection`, `mark_offline`, `has_mount`; module-level `get_registry`/`set_registry` for test injection; `generate_mount_code()` using `secrets.token_urlsafe(6)`
- `relay/app/main.py` — `create_relay_app()` factory with CORS middleware and landing router
- `pyproject.toml` — relay added to `[tool.hatch.build.targets.wheel] packages`

### Task 2: Templates and landing router

- `relay/templates/base.html` — shared layout with system font stack, centered `.card`, light/dark via `prefers-color-scheme`
- `relay/templates/landing.html` — info + mount code input form
- `relay/templates/not_found.html` — "Mount Not Found" with code retry input
- `relay/templates/offline.html` — "This mount is currently offline. The owner may reconnect soon."
- `relay/templates/expired.html` — "This mount has expired and is no longer accessible."
- `relay/app/routers/landing.py` — GET / handler: non-empty code → 302 redirect to `/m/{code}/`, empty code → landing template. Exports `templates` for Plan 02 reuse.

## Test Results

33 tests passing across two test files:
- `tests/relay/test_mount_registry.py` — 20 tests covering all registry lifecycle states
- `tests/relay/test_landing.py` — 13 tests covering GET /, redirect, empty code, and template smoke tests

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Key files verified present:
- relay/app/services/mount_registry.py: FOUND
- relay/app/routers/landing.py: FOUND
- relay/templates/base.html: FOUND
- relay/templates/not_found.html: FOUND
- tests/relay/test_mount_registry.py: FOUND
- tests/relay/test_landing.py: FOUND

Commits verified:
- 8f7ab6c: feat(09-01): relay package foundation
- 6e047f5: feat(09-01): landing page, error templates, and landing router
