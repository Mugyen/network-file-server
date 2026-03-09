# Keyboard Shortcuts

## Summary
Power-user keyboard shortcuts for the file browser. Navigate, select, upload, delete, and rename without touching the mouse.

## Why This Matters
The file browser is a table — keyboard navigation is the natural interaction model. Power users (developers, sysadmins) expect it. Without shortcuts, every action requires a mouse click, which is slow for repetitive tasks.

## Implementation
- `?` or `/` — open shortcuts reference modal
- `↑` / `↓` — move selection cursor
- `Space` — toggle checkbox on focused row
- `Enter` — open folder or preview file
- `Backspace` / `←` — navigate up a directory
- `Ctrl+A` — select all
- `Delete` — delete selected files (with confirmation)
- `F2` or `r` — rename focused file inline
- `U` — trigger upload dialog
- `N` — new folder dialog
- Escape — dismiss modals / clear selection
- Shortcuts disabled when a text input is focused

## Scope
Small — 2-4 hours. Pure frontend, no backend changes needed.

## Monetization
Free tier. Developer-facing polish.
