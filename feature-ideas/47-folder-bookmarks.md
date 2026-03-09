# Folder Bookmarks

## Summary
Bookmark frequently accessed deep folders for one-click navigation. Bookmarks persist in localStorage and appear in a sidebar or dropdown for instant access.

## Why This Matters
When serving a large directory tree, navigating to the same deeply nested folder repeatedly (e.g. `Projects/ClientX/Assets/2026/March/`) is tedious. Bookmarks reduce that to one click.

## Implementation
- "Bookmark this folder" button in the breadcrumb bar (star icon)
- Bookmarks stored in `localStorage` (client-side, per browser)
- Bookmarks panel: collapsible sidebar section or dropdown in the header
- Each bookmark shows folder name + truncated path
- Click bookmark → navigate directly to that path (sets `?path=` param)
- Drag to reorder bookmarks
- Right-click bookmark → remove
- Max 20 bookmarks with graceful overflow handling

## Scope
Tiny-small — 1-3 hours. Pure frontend, no backend changes.

## Monetization
Free tier. Navigation polish for power users.
