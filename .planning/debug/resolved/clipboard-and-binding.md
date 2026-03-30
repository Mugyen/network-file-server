---
status: resolved
trigger: "Two related issues: no copy-to-clipboard button in scratchpad; relay only accessible via localhost"
created: 2026-03-16T00:00:00Z
updated: 2026-03-30T00:00:00Z
---

## Current Focus

hypothesis: confirmed and verified (both fixes already applied in prior commits)
test: n/a
expecting: n/a
next_action: archive session

## Symptoms

expected: (1) Scratchpad/clipboard panel has a button to copy snippet content to device clipboard, especially for mobile. (2) Relay server is accessible from other devices on the network.
actual: (1) No copy button exists anywhere in the scratchpad UI. (2) Relay binds to 127.0.0.1 (localhost only), unreachable from other devices.
errors: none (functional gaps, not crashes)
reproduction: (1) Open scratchpad panel, observe no copy button on any snippet card. (2) Start relay with documented command, try to access from another device on LAN.
started: always (features were never implemented/configured)

## Evidence

- timestamp: 2026-03-16T00:00:00Z
  checked: client/src/components/SnippetCard.tsx (full file, 94 lines)
  found: The SnippetCard component renders a collapse/expand toggle, an editable title input, a delete button, and a textarea for content. There is NO copy-to-clipboard button anywhere in the component. The only action buttons are collapse (ChevronDown/ChevronRight), and delete (X icon). The lucide-react icon library is already imported but no Copy/Clipboard icon is used.
  implication: A copy button needs to be added to SnippetCard.tsx, likely using the navigator.clipboard.writeText() API.

- timestamp: 2026-03-16T00:00:00Z
  checked: client/src/components/ScratchpadPanel.tsx (full file, 103 lines)
  found: The panel renders a header (with add/close buttons) and maps over snippets rendering SnippetCard for each. No copy functionality exists at the panel level either. The readOnly prop is passed through to each card but copy should work regardless of readOnly status.
  implication: Copy button belongs in SnippetCard (per-snippet), not at the panel level.

- timestamp: 2026-03-16T00:00:00Z
  checked: relay/app/main.py (full file, 41 lines)
  found: The relay app is a pure FastAPI app factory (create_relay_app). It creates the FastAPI instance, adds CORS middleware, includes routers, and exports `app = create_relay_app()`. There is NO uvicorn.run() call, NO CLI, NO __main__.py for the relay package. The relay has no built-in way to configure host binding.
  implication: The relay is started externally via `uv run uvicorn relay.app.main:app --port 8001`. The binding address depends entirely on the CLI invocation.

- timestamp: 2026-03-16T00:00:00Z
  checked: .planning/phases/11-remote-access-and-hardening/.continue-here.md line 55
  found: Documented relay startup command is `uv run uvicorn relay.app.main:app --port 8001` with NO --host flag. Uvicorn defaults to `127.0.0.1` when --host is not specified.
  implication: The relay is unreachable from other devices because the documented startup command omits `--host 0.0.0.0`. This is a documentation/startup-config issue. Could be fixed by either (a) updating docs to include `--host 0.0.0.0`, or (b) adding a relay CLI entry point that defaults to 0.0.0.0 like the main server does (see server/app/cli.py line 191).

- timestamp: 2026-03-30T00:00:00Z
  checked: Current state of SnippetCard.tsx (127 lines), relay/cli.py, pyproject.toml, README.md
  found: Both fixes were already applied in prior commits. SnippetCard.tsx now has a copy button (Copy/Check icons, handleCopy with navigator.clipboard + execCommand fallback, 1500ms checkmark feedback). relay/cli.py exists with argparse, defaults host to 0.0.0.0, and is registered as `network-relay` console script in pyproject.toml. README documents `uv run network-relay` binding 0.0.0.0:8001.
  implication: No code changes needed. Session can be verified and resolved.

- timestamp: 2026-03-30T00:00:00Z
  checked: Verification via CLI and TypeScript compilation
  found: `uv run network-relay --help` works correctly, shows default 0.0.0.0. TypeScript compiles cleanly (npx tsc --noEmit returns no errors).
  implication: Both fixes are functional and verified.

## Eliminated

(none -- both root causes confirmed on first investigation)

## Resolution

root_cause: |
  Two separate issues:

  1. **Missing copy button (UI gap):** SnippetCard.tsx had no copy-to-clipboard button.
     The component only had collapse/expand and delete actions. The navigator.clipboard
     API was never called anywhere in the clipboard/scratchpad feature.

  2. **Relay localhost binding (config gap):** The relay had no CLI entry point of its own.
     It was started via bare uvicorn command defaulting to 127.0.0.1.

fix: |
  Both fixes were applied in prior commits on this branch:

  1. **Copy button** (commit 3c9ee07): Added handleCopy() to SnippetCard with
     navigator.clipboard.writeText() + execCommand fallback for HTTP-over-LAN.
     Copy/Check icons from lucide-react. 1500ms checkmark feedback. Works in
     both readOnly and editable modes.

  2. **Relay CLI** (commit c0e8ca3): Created relay/cli.py with argparse, defaulting
     host to 0.0.0.0. Registered as `network-relay` console script in pyproject.toml.
     README updated to document `uv run network-relay`.

verification: |
  - relay/cli.py imports correctly
  - `uv run network-relay --help` shows default 0.0.0.0 binding
  - TypeScript compiles with no errors (npx tsc --noEmit)
  - SnippetCard.tsx has Copy button with secure context + fallback pattern

files_changed:
  - client/src/components/SnippetCard.tsx (commit 3c9ee07)
  - relay/cli.py (commit c0e8ca3)
  - pyproject.toml (commit c0e8ca3)
  - README.md (updated relay docs)
