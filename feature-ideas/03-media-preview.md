# In-Browser Media Preview

## Summary
Preview files directly in the browser without downloading. Stream video/audio, view images in a lightbox, render PDFs, display code with syntax highlighting, preview markdown.

## Why This Matters
Transforms the server from a file list into a media hub. Users can browse photos, watch videos, or review documents without cluttering their Downloads folder. This is what makes it feel like a real product.

## Implementation
- Image preview: lightbox with zoom, pan, slideshow mode
- Video/audio: HTML5 player with streaming (range request support)
- PDF: embedded viewer using PDF.js or native browser rendering
- Code files: syntax-highlighted viewer (highlight.js or Prism)
- Markdown: rendered HTML preview
- Text files: simple viewer with line numbers
- Office docs: basic preview via iframe or conversion

## Scope
Medium-large — 5-8 hours. Each file type is incremental work.

## Monetization
Free tier (images, text, PDF). Pro tier: video streaming, office docs, slideshow mode.
