# Network Speed Test & Optimization

## Summary
Built-in speed test between the server and connected devices. Shows real-time transfer speeds, network quality indicators, and suggestions for optimization (e.g., "Move closer to router" or "Switch to 5GHz").

## Why This Matters
Users blame the app when transfers are slow, even if it's their network. A speed test sets expectations, builds trust, and provides actionable advice. It's also a cool demo feature that impresses people.

## Implementation
- Speed test endpoint: download/upload a test payload and measure throughput
- Display results: download speed, upload speed, latency
- Network quality indicator on the main UI (green/yellow/red)
- Per-transfer speed display (live Mbps during upload/download)
- Historical speed chart (track network performance over time)
- Optimization tips based on results
- Estimated transfer time for pending files based on current speed
- Compression suggestion: "Enable compression to save 40% bandwidth"

## Scope
Small — 2-3 hours. Simple payload transfer + timing.

## Monetization
Free tier. Trust-building feature that reduces support burden.
