---
status: diagnosed
trigger: "Two related issues: no copy-to-clipboard button in scratchpad; relay only accessible via localhost"
created: 2026-03-16T00:00:00Z
updated: 2026-03-16T00:00:00Z
---

## Current Focus

hypothesis: confirmed (two separate root causes identified)
test: n/a
expecting: n/a
next_action: hand off for fixing

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

## Eliminated

(none -- both root causes confirmed on first investigation)

## Resolution

root_cause: |
  Two separate issues:

  1. **Missing copy button (UI gap):** SnippetCard.tsx has no copy-to-clipboard button.
     The component only has collapse/expand and delete actions. The navigator.clipboard
     API is never called anywhere in the clipboard/scratchpad feature. This is a missing
     feature, not a bug.

  2. **Relay localhost binding (config gap):** The relay has no CLI entry point of its own.
     It is started via bare uvicorn command: `uv run uvicorn relay.app.main:app --port 8001`.
     Uvicorn defaults to binding on 127.0.0.1 when no --host is specified. The main server
     (server/app/cli.py:191) defaults to 0.0.0.0, but the relay has no equivalent.

fix: (not applied -- diagnosis only)
verification: (not applied)
files_changed: []

## Affected Files

### Issue 1: Copy button
- `client/src/components/SnippetCard.tsx` -- needs a copy button added per snippet card
  - Add a Copy icon from lucide-react (e.g., `Copy` or `Clipboard`)
  - Call `navigator.clipboard.writeText(snippet.content)` on click
  - Show brief visual feedback (checkmark or tooltip) on successful copy
  - Should work in both readOnly and editable modes

### Issue 2: Relay binding
- Option A (minimal): Update documentation/startup instructions to use `--host 0.0.0.0`
  - `.planning/phases/11-remote-access-and-hardening/.continue-here.md` line 55
  - `README.md` (if relay startup is documented there)
- Option B (proper): Add a relay CLI entry point similar to server/app/cli.py
  - Create `relay/cli.py` or `relay/__main__.py`
  - Default host to `0.0.0.0` (matching server behavior at server/app/cli.py:191)
  - Accept `--port` and `--host` arguments
  - Register as a console script in pyproject.toml
