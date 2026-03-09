# Drag-and-Drop Upload & Batch Operations

## Summary
Real drag-and-drop file upload with progress bars. Multi-select files for batch download (as ZIP), batch delete, and batch move. Folder creation and file renaming.

## Why This Matters
These are table-stakes features users expect from any file manager. Without them, power users bounce immediately. The current upload UX is clunky — drag-and-drop with progress tracking is the minimum bar.

## Implementation
- Drag-and-drop zone using HTML5 Drag and Drop API
- Multi-file upload with individual progress bars (chunked upload for large files)
- Batch select via checkboxes or shift-click
- "Download as ZIP" for selected files (use Python `zipfile` module, stream the response)
- Delete files (with confirmation dialog)
- Rename files inline
- Create new folders, navigate into subdirectories
- Move files between folders (drag into folder)

## Scope
Medium — 4-6 hours. Each operation is small but there are many.

## Monetization
Free tier. These are expected features, not premium.
