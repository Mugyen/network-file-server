# Search, Filter & Sort

## Summary
Full-text search across filenames, instant filtering by file type, and multiple sort options (name, size, date, type). Essential for navigating large shared folders.

## Why This Matters
The current server shows all files in alphabetical order with no way to find anything specific. Once a shared folder has 50+ files, it becomes unusable. Search and filter are the basics that make it scale.

## Implementation
- Instant search bar with live filtering (client-side for speed)
- Search by filename, extension, or file content (for text files)
- Filter chips: Images, Videos, Documents, Audio, Archives, Code, Other
- Sort options: Name (A-Z / Z-A), Size (largest/smallest), Date (newest/oldest), Type
- Persistent sort/filter preferences (localStorage)
- URL query parameters for shareable filtered views
- Keyboard shortcut: Cmd/Ctrl+K to focus search
- Search result highlighting
- Advanced: fuzzy matching for typo-tolerant search
- Advanced: tag system for manual file categorization

## Scope
Small-medium — 3-5 hours. Client-side filtering is fast to build.

## Monetization
Free tier. This is a usability essential, not a premium feature.
