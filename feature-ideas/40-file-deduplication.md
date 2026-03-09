# File Deduplication

## Summary
Detect duplicate files by content hash before and after uploads. Surface duplicates in the UI and optionally auto-skip uploading files that already exist on the server.

## Why This Matters
Uploading duplicates is a common source of clutter, especially when multiple people upload to the same folder. Users waste time and disk space on files that are already there.

## Implementation
- Hash files on upload (SHA-256, streamed — no full file in memory)
- Check hash against an in-memory index of already-served files
- On duplicate detected: show warning with link to existing file, offer skip/overwrite/rename
- `GET /api/files/duplicates` endpoint — scan a directory and return groups of duplicate files
- UI: "Find Duplicates" action in toolbar, shows grouped results with checkboxes to delete extras
- Hash index built lazily on first scan, invalidated on file changes

## Scope
Medium — 4-6 hours. Hashing is cheap; the UI for reviewing duplicates is the bulk of the work.

## Monetization
Pro tier. Useful for media-heavy workflows (photographers, video editors).
