# QR Code Instant Connect

## Summary
Generate a QR code containing the server URL — displayed both in the terminal (ASCII art) and on the web UI. Any device on the network scans it and instantly opens the file server. Zero typing, zero config.

## Why This Matters
The #1 friction point is telling someone "go to 192.168.1.47:6969." QR eliminates that entirely. This is the "wow" moment that gets people to share the product.

## Implementation
- Use `qrcode` Python library to generate QR from `http://<local-ip>:<port>`
- Render ASCII QR in terminal on server start
- Show QR as SVG/PNG on the web UI (useful for projecting on a screen)
- Auto-refresh QR if IP changes

## Scope
Small — 1-2 hours. High impact for minimal effort.

## Monetization
Free tier. This is the viral hook.
