# Progressive Web App (PWA) for Mobile

## Summary
Make the web UI installable as a PWA on phones and tablets. Add share-target support so users can "Share to WiFi Server" from any app — photos, documents, links, anything.

## Why This Matters
PWA installation puts your app on the home screen alongside native apps. Share-target integration means users can share from their camera roll, browser, or any app directly to the server. This eliminates the "open browser, navigate to IP" friction entirely.

## Implementation
- Service worker for offline shell caching
- Web app manifest with icons, theme colors, display mode
- Share Target API: register as a share target for files, text, URLs
- Web Share API: share files FROM the server to other apps
- Push notifications for upload completion, new files available
- Background sync for queued uploads on flaky connections
- Camera integration: "Take Photo & Upload" button
- Contact picker for sharing access links
- Installability prompt with custom banner

## Scope
Medium — 5-8 hours. Manifest + service worker + share target.

## Monetization
Free tier (basic PWA). Pro tier: share target, push notifications, camera integration.
