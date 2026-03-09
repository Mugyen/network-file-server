# Expiring Share Links

## Summary
Generate temporary, shareable links for specific files or folders. Links expire after a configurable time or number of downloads. Password-optional. Works even with the secure tunnel feature.

## Why This Matters
"Share this file with someone" is the most common request. Instead of sharing access to the entire server, users can share a single-file link that auto-expires. This is how WeTransfer, Dropbox links, and Google Drive sharing work — but self-hosted and private.

## Implementation
- Generate unique short URL for any file/folder (e.g., `/s/abc123`)
- Configurable expiry: 1 hour, 24 hours, 7 days, custom, never
- Download limit: expire after N downloads
- Optional password protection
- Link management dashboard: see all active links, revoke any time
- Copy-to-clipboard button for generated links
- QR code for each share link
- Recipient doesn't need to access the main server UI
- Custom landing page for shared links (download button + file info)
- Email integration: send share link via email directly from UI

## Scope
Medium — 5-7 hours. Token generation, storage, and expiry logic.

## Monetization
Pro tier. Share links are a power-user feature with clear value.
