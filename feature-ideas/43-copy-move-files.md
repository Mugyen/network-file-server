# Copy & Move Files

## Summary
Copy or move files and folders between directories entirely on the server — no download/re-upload required. Drag-and-drop between folders or use the context menu.

## Why This Matters
A basic file manager operation that's conspicuously missing. Without it, reorganizing files requires downloading to your device and re-uploading, which is slow and wastes bandwidth.

## Implementation
- `POST /api/files/move` — `{paths: [...], destination: "..."}` (uses `shutil.move`)
- `POST /api/files/copy` — `{paths: [...], destination: "..."}` (uses `shutil.copy2`)
- Both endpoints validate source and destination paths through `resolve_safe_path`
- Conflict resolution on destination: overwrite / skip / rename (reuses existing logic)
- UI: context menu "Move to…" / "Copy to…" opens a folder picker modal
- Drag-and-drop: drag selected files onto a folder row in the table to move them
- Progress via WebSocket for large directory copies

## Scope
Medium — 4-6 hours. Backend is straightforward; folder picker UI is the main effort.

## Monetization
Free tier. A core file management operation — should be in the base product.
