# WebRTC Peer-to-Peer Transfer

## Summary
Direct device-to-device file transfers using WebRTC data channels. The server acts only as a signaling broker — actual file data flows directly between browsers at maximum network speed.

## Why This Matters
With the current architecture, all data flows through the Python server — it's a bottleneck. WebRTC enables direct transfers at full network speed, handles NAT traversal, and works even if the server is on a low-power device (like a Raspberry Pi). This is what makes it competitive with Snapdrop/ShareDrop but self-hosted and feature-rich.

## Implementation
- WebSocket signaling server for connection brokering
- WebRTC data channel for file transfer
- Chunked transfer with progress tracking
- Automatic fallback to server relay if P2P fails (TURN-like)
- Device discovery: show all connected devices with names/icons
- "Send to device" button for direct transfers
- Support for multiple simultaneous transfers

## Scope
Large — 10-15 hours. WebRTC plumbing is the hard part.

## Monetization
Pro tier. Speed advantage is tangible and demonstrable.
