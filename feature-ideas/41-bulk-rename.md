# Bulk Rename

## Summary
Rename multiple selected files at once using a pattern template — add a prefix, suffix, sequential numbering, or date stamp without renaming each file individually.

## Why This Matters
A common task after downloading photos from a camera or receiving files from multiple sources: "rename all these to IMG_001, IMG_002, …" or "prefix them all with the project name." Doing it one-by-one is painful.

## Implementation
- Select files → "Bulk Rename" in batch toolbar
- Pattern editor with live preview of all resulting names:
  - `{name}` — original filename without extension
  - `{ext}` — file extension
  - `{n}` — sequential number (configurable start + padding)
  - `{date}` — today's date (configurable format)
  - Free-text prefix/suffix fields
- Preview table: original name → new name for each selected file
- Conflict detection: warn if any resulting names collide
- Single API call: `POST /api/files/bulk-rename` with a list of `{path, new_name}` pairs

## Scope
Medium — 4-6 hours. Pattern engine + preview UI are the interesting parts.

## Monetization
Pro tier. Power-user feature for photographers and content creators.
