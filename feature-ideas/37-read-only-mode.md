# Read-Only Mode

## Summary
A `--read-only` CLI flag that disables all write operations (upload, delete, rename, create folder, clipboard writes, file requests). Safe for sharing files without risk of accidental modification.

## Why This Matters
Common use case: "Here's my laptop, browse and download whatever you need" — but you don't want guests deleting or overwriting anything. One flag should make the server safe to hand to someone.

## Implementation
- `--read-only` CLI flag passed at startup
- Backend middleware rejects all mutating HTTP methods (POST, PUT, PATCH, DELETE) with 403
- Frontend detects read-only mode via a `GET /api/server-info` flag
- Upload button, delete button, rename, and create folder are hidden in the UI
- Clipboard and file request panels hidden or shown as read-only
- Clear visual indicator in the UI header ("Read-only mode")

## Scope
Small — 2-3 hours. Mostly a middleware flag + UI conditional rendering.

## Monetization
Free tier. A safety feature that increases trust and adoption.
