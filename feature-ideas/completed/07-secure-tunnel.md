# Remote Access via Secure Tunnel

## Summary
One-click tunnel to share files beyond the local network. Generates a temporary public URL (like ngrok) so anyone on the internet can access your shared folder. Time-limited, password-protected.

## Why This Matters
Local-only access is the biggest limitation. Freelancers sending deliverables, remote teams sharing files, friends sharing media — all need internet access. A single "Share publicly" button transforms this from a local tool to a universal one.

## Implementation
- Integrate with Cloudflare Tunnel (free, no account needed for quick tunnels)
- Alternative: ngrok, localtunnel, or bore as fallback options
- One-click "Go Public" button in the web UI
- Auto-generate a shareable URL displayed prominently
- Configurable expiry (1 hour, 24 hours, custom)
- Optional password protection layer
- Bandwidth/download limits to prevent abuse
- Kill switch to instantly revoke access
- Activity log showing who accessed what

## Scope
Medium — 4-6 hours. Most tunneling tools have simple CLIs.

## Monetization
Pro tier. Clear premium value — this unlocks a whole new use case.
