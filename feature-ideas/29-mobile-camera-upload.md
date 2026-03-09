# Mobile Camera Direct Upload

## Summary
"Take Photo & Upload" button in the mobile web UI. Opens the device camera, takes a photo or video, and uploads it directly to the server. No saving to camera roll, no file picker — one tap.

## Why This Matters
The most common mobile-to-computer transfer is photos. Currently users must: take photo -> open browser -> navigate to server -> tap upload -> find photo in picker -> upload. This feature reduces it to: open app -> tap camera -> done. Event photographers, inventory managers, and field workers would use this daily.

## Implementation
- Camera button in the mobile UI using `<input type="file" capture="environment">`
- Live camera preview using MediaDevices API for a richer experience
- Photo capture with optional front/rear camera toggle
- Video recording with duration indicator
- Auto-upload immediately after capture (no confirmation step, or optional review)
- Burst mode: take multiple photos rapidly
- Auto-naming: timestamp-based filenames with configurable prefix
- Auto-organize: upload to date-based folders (e.g., `2026-03-09/`)
- EXIF preservation: keep location, orientation, camera metadata
- Optional image quality/resolution settings (reduce size before upload)

## Scope
Small-medium — 3-5 hours. HTML5 camera APIs do the heavy lifting.

## Monetization
Free tier. This drives mobile adoption and makes the product stickier.
