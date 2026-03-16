# Receive Mode / Digital Drop Box

## Summary
A "send me files" mode — generate a link that lets anyone upload files to your machine. Like a digital drop box. Time-limited, password-protected, with configurable size limits.

## Why This Matters
Unique angle that most local file servers don't offer. Clear use cases: teachers collecting assignments, photographers receiving client selections, event organizers collecting photos from guests, freelancers receiving assets from clients. Each of these is a repeatable paid use case.

## Implementation
- New `/dropbox` mode with a clean, branded upload-only interface
- Customizable welcome message ("Upload your photos here!")
- Password protection (optional)
- Expiry time (auto-disable after N hours)
- File size limits and allowed file type restrictions
- Upload confirmation with thank-you message
- Host gets real-time notifications (browser notification + sound) on new uploads
- Auto-organize uploads into timestamped folders or by uploader name
- Shareable short link / QR code for the drop box
- Rate limiting to prevent abuse

## Scope
Medium — 5-7 hours. It's a simplified view with access controls.

## Monetization
Pro tier. Each use case (teacher, photographer, etc.) is a distinct market segment.
