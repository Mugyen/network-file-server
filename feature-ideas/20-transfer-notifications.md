# Real-Time Transfer Notifications

## Summary
Live notifications when files are uploaded, downloaded, or when new devices connect. Notifications appear as browser push notifications, in-app toasts, and optional sounds.

## Why This Matters
Without notifications, the server admin has no idea what's happening. Did that large file finish uploading? Did someone download the project files? Real-time feedback builds trust and makes the server feel alive.

## Implementation
- WebSocket connection for real-time event streaming
- In-app toast notifications (bottom-right corner)
- Browser Push Notification API integration (with permission prompt)
- Notification types: file uploaded, file downloaded, device connected, device disconnected
- Notification settings: toggle per event type, sound on/off
- Notification history panel (last 50 events)
- Desktop notification support via Notification API
- Optional sound effects (subtle, professional)
- Admin: see all activity in real-time feed
- Webhook support: POST to external URL on events

## Scope
Medium — 4-6 hours. WebSocket infrastructure is reusable across features.

## Monetization
Free tier (basic toasts). Pro tier: push notifications, webhook, activity feed.
