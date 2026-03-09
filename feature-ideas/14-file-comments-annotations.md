# File Comments & Annotations

## Summary
Add comments and annotations to shared files. Leave notes on images (pin-point annotations), comment threads on documents, and feedback on any file type. Like Google Drive comments but local.

## Why This Matters
Turns passive file sharing into active collaboration. Designers can get feedback on mockups, teams can discuss documents, teachers can annotate student submissions. This creates engagement loops that keep users coming back.

## Implementation
- Comment thread per file (stored in a local SQLite database)
- Image annotations: click on a point in the image to leave a comment
- PDF annotations: highlight text and comment
- @mentions with notifications
- Resolve/unresolve comment threads
- Comment history and edit tracking
- Anonymous commenting option (for drop box mode)
- Export comments as PDF/text summary

## Scope
Medium-large — 8-12 hours. Image annotation is the complex part.

## Monetization
Pro tier. Collaboration features justify premium pricing.
