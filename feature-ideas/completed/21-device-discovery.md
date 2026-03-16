# Automatic Device Discovery

## Summary
Automatically discover and display all devices connected to the file server. Show device names, types (phone/laptop/tablet), OS, and connection status. Enable direct device-to-device actions like "Send to iPhone."

## Why This Matters
Knowing who's connected makes the server feel social and interactive. "Send to device" is the AirDrop experience people want. Device awareness also enables security features ("I don't recognize that device — disconnect it").

## Implementation
- Track connected clients via WebSocket heartbeat
- Device fingerprinting: User-Agent parsing for device type, OS, browser
- Custom device naming (users can rename their device)
- Device avatars/icons based on type (phone, laptop, tablet, desktop)
- Online/offline status indicators
- "Send file to [device]" action button
- Connection history: see when devices connected/disconnected
- Admin: block/kick devices
- mDNS/Bonjour broadcast so the server appears in network discovery
- Zero-conf: auto-discover other WiFi File Server instances on the network

## Scope
Medium — 5-7 hours. Device tracking + mDNS are the main pieces.

## Monetization
Free tier (basic device list). Pro tier: send to device, block, history.
