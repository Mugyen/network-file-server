# ZIP / Archive Extraction

## Summary
Extract `.zip`, `.tar.gz`, and `.tar` archives server-side, in place, without downloading them first. Right-click an archive → "Extract here" or "Extract to folder".

## Why This Matters
A common workflow: someone uploads a ZIP of project files, and you want to browse them without downloading the archive to your own machine first. Server-side extraction makes the server feel like a real file manager.

## Implementation
- Context menu option on archive files: "Extract here" / "Extract to subfolder"
- `POST /api/files/extract` endpoint with `{path, destination}` — uses Python's `zipfile` / `tarfile` stdlib
- Streaming extraction with progress via WebSocket (for large archives)
- Conflict resolution on extract: overwrite / skip / rename (reuses existing conflict resolution logic)
- Supported formats: `.zip`, `.tar`, `.tar.gz`, `.tar.bz2`
- Safety: validate that extracted paths don't escape the destination (path traversal guard)

## Scope
Small-medium — 3-5 hours. Python stdlib handles the heavy lifting; UI is minimal.

## Monetization
Free tier (basic zip). Pro tier for large archives + streaming progress.
