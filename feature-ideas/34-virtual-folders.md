# Virtual Folders & Collections

## Summary
Create virtual folders (collections) that group files from different physical locations without moving them. Like smart playlists for files. "Project Alpha" collection can contain files from Downloads, Desktop, and Documents.

## Why This Matters
Physical folder structures are rigid. Users often want to group files by project, event, or purpose across multiple directories. Virtual folders provide flexible organization without restructuring the filesystem. It's how modern users think about files.

## Implementation
- "Create Collection" button
- Drag files into collections (creates virtual links, not copies)
- Collections panel in sidebar
- Collection sharing: share a collection as a single downloadable unit
- Smart collections: auto-populate based on rules (e.g., "all PDFs modified this week")
- Collection metadata: description, icon, color
- Nested collections (collections within collections)
- Pin collections to the top of the UI
- Export collection as ZIP
- Collection-level permissions in multi-user mode

## Scope
Medium — 5-7 hours. Metadata storage + UI for collection management.

## Monetization
Pro tier. Organization features appeal to power users.
