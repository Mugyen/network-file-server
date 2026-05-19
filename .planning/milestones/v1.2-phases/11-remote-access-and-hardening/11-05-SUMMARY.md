---
phase: 11-remote-access-and-hardening
plan: "05"
subsystem: frontend-clipboard,relay-cli
tags: [clipboard, relay, cli, ux]
dependency_graph:
  requires: []
  provides: [copy-to-clipboard-snippet, network-relay-cli]
  affects: [client/src/components/SnippetCard.tsx, relay/cli.py, pyproject.toml]
tech_stack:
  added: []
  patterns: [navigator.clipboard.writeText, argparse-console-scripts]
key_files:
  created:
    - relay/cli.py
  modified:
    - client/src/components/SnippetCard.tsx
    - pyproject.toml
    - docs/project-log.md
    - README.md
key_decisions:
  - "Copy button placed outside readOnly guard — reading clipboard content is always allowed regardless of write permissions"
  - "Relay CLI defaults to 0.0.0.0:8001 — matches server/app/cli.py pattern; explicit None checks avoid default parameters on main()"
metrics:
  duration: 8m
  completed_date: "2026-03-16"
  tasks_completed: 2
  files_modified: 5
---

# Phase 11 Plan 05: Clipboard Copy Button and Relay CLI Summary

**One-liner:** Copy-to-clipboard button on SnippetCard with 1.5s visual feedback, plus `network-relay` CLI that binds to 0.0.0.0:8001 by default.

## What Was Built

### Task 1: SnippetCard copy-to-clipboard button

Added `Copy`/`Check` icons from lucide-react and a `copied` boolean state to `SnippetCard`. The `handleCopy` function calls `navigator.clipboard.writeText(snippet.content)`, flips `copied` to true for 1.5s (showing a green Check icon), then reverts. The button is rendered outside the `!readOnly` guard so it appears in both owner and visitor views.

### Task 2: Relay CLI entry point

Created `relay/cli.py` with a `main()` function using argparse. Registered as `network-relay` console script in `pyproject.toml`. Defaults: host=0.0.0.0, port=8001 (set via explicit None checks — no default parameters on the function per project conventions). Updated README to document `uv run network-relay` and its flags.

## Verification

- `cd client && npx tsc --noEmit` — clean, no errors
- `uv run network-relay --help` — shows --host and --port flags
- `uv run pytest tests/ -x -q` — 208 passed

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- relay/cli.py exists: FOUND
- client/src/components/SnippetCard.tsx contains navigator.clipboard.writeText: FOUND
- pyproject.toml contains network-relay entry: FOUND
- Commits 3c9ee07 and c0e8ca3: FOUND
