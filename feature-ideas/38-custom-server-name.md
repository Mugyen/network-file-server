# Custom Server Name

## Summary
Set a friendly name for the server via a `--name` CLI flag. The name appears in the browser tab, the QR code landing page, and the UI header — instead of a bare IP address.

## Why This Matters
"192.168.1.42:8000" is forgettable and impersonal. "Rahul's MacBook" or "Photo Booth Uploads" immediately tells guests where they are and what to do. Small polish, big first impression.

## Implementation
- `--name` CLI flag (e.g. `--name "Photo Booth"`)
- Name exposed via `GET /api/server-info`
- Shown in: browser `<title>`, UI header/navbar, QR code landing page subtitle
- Default: hostname of the machine (e.g. `Rahul's MacBook`)
- Optional: editable from the UI and persisted in a local config file

## Scope
Tiny — 1-2 hours. Mostly passing a string through to the frontend.

## Monetization
Free tier. Pure polish.
