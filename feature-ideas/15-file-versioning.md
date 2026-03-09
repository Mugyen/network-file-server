# File Versioning & History

## Summary
Track file versions automatically. Every upload of a file with the same name creates a new version instead of rejecting the duplicate. Browse version history, compare versions, and restore any previous version.

## Why This Matters
Currently the server rejects duplicate filenames — the worst possible behavior. Versioning turns this weakness into a feature. Designers iterating on mockups, writers revising documents, developers sharing builds — all need version history.

## Implementation
- Store versions in a hidden `.versions/` directory alongside original files
- Auto-version on upload of duplicate filename (v1, v2, v3...)
- Version history panel in the UI: list all versions with timestamps and sizes
- One-click restore to any previous version
- Diff view for text files (show what changed between versions)
- Side-by-side image comparison for image files
- Configurable retention policy: keep last N versions, or versions from last N days
- Storage usage display per file (all versions combined)
- Option to permanently delete old versions

## Scope
Medium — 5-8 hours. Storage management logic is the core work.

## Monetization
Pro tier. Version history is a universally valued feature.
