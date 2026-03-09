# Auto-Sync Folders

## Summary
Watch a folder on device A and automatically sync changes to device B over the local network. A lightweight, self-hosted Dropbox/Syncthing alternative with zero cloud dependency.

## Why This Matters
Developers syncing code between machines, photographers offloading from camera to NAS, families keeping a shared photo folder in sync — ongoing sync is stickier than one-time transfers. Users who set this up never leave.

## Implementation
- File system watcher (watchdog library) to detect changes
- Delta sync: only transfer changed files (compare checksums)
- Conflict resolution strategy (last-write-wins, keep-both, or prompt)
- Bidirectional or unidirectional sync modes
- Sync status dashboard showing pending/completed/failed transfers
- Bandwidth throttling to avoid saturating the network
- Exclude patterns (e.g., `.git/`, `node_modules/`)
- Sync history log
- Pause/resume sync

## Scope
Large — 12-20 hours. File watching and conflict resolution are complex.

## Monetization
Pro tier. This is a standalone product-level feature.
