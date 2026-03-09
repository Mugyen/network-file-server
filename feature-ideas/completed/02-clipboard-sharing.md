# Cross-Device Clipboard Sharing

## Summary
Share text snippets, URLs, code blocks, and small data across devices in real-time. A universal clipboard between your phone, laptop, and tablet — all over local WiFi.

## Why This Matters
File sharing is occasional. Clipboard sharing is daily. People constantly copy links, passwords, code snippets, and addresses between devices. This makes the server a daily-use tool instead of an occasional utility.

## Implementation
- New `/clipboard` page with a text area and "Copy" / "Paste" buttons
- WebSocket-based real-time sync — paste on one device, it appears on all others
- Clipboard history (last N items) with one-click copy
- Auto-detect URLs and make them clickable
- Auto-detect code and apply syntax highlighting
- Optional: browser Clipboard API integration for true system clipboard sync

## Scope
Medium — 3-5 hours. WebSocket setup is the bulk of the work.

## Monetization
Free tier (basic text sharing). Pro tier: clipboard history, auto-expire, encrypted clips.
