# Smart Photo & Video Gallery

## Summary
Automatic gallery view for image and video files. Grid layout with thumbnails, lightbox viewing, slideshow mode, and basic organization (by date, folder, type). Like Google Photos but local and private.

## Why This Matters
Photo sharing is one of the top use cases for local file servers (event photos, family gatherings, travel pics). A dedicated gallery mode with thumbnails and slideshows is dramatically better than a file list. This is the feature that makes non-technical users love the product.

## Implementation
- Auto-detect folders containing images/videos
- Thumbnail generation (PIL/Pillow) with caching
- Masonry grid layout (like Pinterest/Google Photos)
- Lightbox with swipe navigation (touch-friendly)
- Slideshow mode with configurable interval
- EXIF data extraction: date, location, camera info
- Sort by date taken, name, size
- Filter by file type (photos, videos, both)
- Lazy loading for large galleries
- Video thumbnail extraction (ffmpeg)
- Optional: face detection grouping, location map view

## Scope
Medium — 6-10 hours. Thumbnail generation and caching are the bulk.

## Monetization
Free tier (basic gallery). Pro tier: slideshow, EXIF, video thumbnails.
