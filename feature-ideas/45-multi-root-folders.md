# Multi-Root Folder Serving

## Summary
Serve multiple directories simultaneously from a single server instance. Each root appears as a top-level folder in the UI. No need to run multiple server processes.

## Why This Matters
A common scenario: "I want to share my Downloads folder AND my project folder, but not my entire home directory." Currently you'd have to pick one or run two servers on different ports.

## Implementation
- CLI accepts multiple paths: `uv run wifi-file-server ~/Downloads ~/Projects`
- Each path becomes a named root in the API (using the folder's basename)
- `GET /api/files` at the top level lists the roots, not files
- Navigation below each root works exactly as today
- `resolve_safe_path` validates against all configured roots
- UI breadcrumbs show the root name as the first segment
- QR code landing page lists all available roots

## Scope
Small-medium — 3-5 hours. Mostly a config change + updated path resolution logic.

## Monetization
Free tier. A practical usability improvement for the core product.
