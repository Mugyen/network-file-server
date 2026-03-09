# On-the-Fly File Compression

## Summary
Automatically compress files during transfer to reduce bandwidth usage. Support gzip for text-based files, and offer "Download as ZIP" for multiple files or entire folders.

## Why This Matters
WiFi bandwidth is shared and limited. Compressing text files, code, logs, and documents during transfer can reduce size by 60-90%. "Download folder as ZIP" is a universally expected feature. Together, these make the server dramatically faster for common use cases.

## Implementation
- Gzip Content-Encoding for text-based file downloads (automatic, transparent)
- "Download as ZIP" button for selected files
- "Download folder as ZIP" for entire directories
- Streaming ZIP generation (don't buffer entire ZIP in memory)
- Compression level toggle: fast vs. small
- Display original vs. compressed size in transfer UI
- Auto-compress uploads option (save storage on server)
- Support for existing archives: browse contents of ZIP/tar files without extracting

## Scope
Small-medium — 3-5 hours. Flask gzip middleware + zip streaming.

## Monetization
Free tier (gzip). Pro tier: browse archives, configurable compression.
