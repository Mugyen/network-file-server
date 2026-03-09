# Resumable & Chunked Transfers

## Summary
Support resumable uploads and downloads. If a transfer is interrupted (network drop, browser close, device sleep), it picks up where it left off instead of restarting from zero.

## Why This Matters
Large files over WiFi are unreliable. A 2GB video that fails at 95% and has to restart is infuriating. Resumable transfers are the difference between "this works" and "this is reliable." Essential for the tool to be trusted with important files.

## Implementation
- Chunked upload: split files into chunks (e.g., 5MB), upload individually, reassemble on server
- Upload progress tracking with percentage, speed, and ETA
- Resume upload: track which chunks are received, skip completed ones
- HTTP Range requests for download resumption (partial content support)
- Download progress via Streams API or Content-Length tracking
- Transfer queue: queue multiple files, process sequentially or in parallel
- Pause/resume button for active transfers
- Transfer history with status (completed, failed, in-progress)
- Integrity verification: checksum comparison after transfer completes
- Automatic retry on transient failures (with exponential backoff)

## Scope
Medium-large — 8-12 hours. Chunked upload protocol is the main effort.

## Monetization
Pro tier. Reliability is premium-worthy for anyone transferring large files.
