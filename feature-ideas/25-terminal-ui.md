# Rich Terminal UI

## Summary
A beautiful, informative terminal interface using Rich or similar library. Show server status, active transfers, connected devices, and recent activity — all in the terminal. No browser needed for the admin.

## Why This Matters
The terminal is where the server runs. Currently it just prints a URL and goes silent. A rich terminal UI makes the admin experience delightful and gives instant visibility into what's happening. Power users and developers will love it.

## Implementation
- Rich library for formatted terminal output
- Startup banner with ASCII art logo, server URL, and QR code
- Live dashboard panels:
  - Server status (uptime, port, shared folder, storage used)
  - Connected devices (name, IP, type, last activity)
  - Active transfers (filename, progress bar, speed)
  - Recent activity log (last 20 events)
- Color-coded log messages (upload=green, download=blue, error=red)
- Keyboard controls: q=quit, r=refresh, c=clear logs
- Minimal mode: just essential info for embedding in scripts
- JSON output mode for programmatic consumption

## Scope
Small-medium — 3-5 hours. Rich library handles most of the rendering.

## Monetization
Free tier. This is the developer-facing polish that drives GitHub stars.
