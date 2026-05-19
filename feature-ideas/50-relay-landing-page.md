# Relay Landing Page & Mount Code Entry

## Summary
A polished public-facing landing page at the relay root URL with a "Enter mount code" form, project branding, and OpenGraph meta tags for social sharing.

## Why This Matters
When someone visits the relay URL (from a Reddit post, shared link, or bookmark), they currently see nothing useful. The landing page is the first impression — it needs to explain what the project is, let users enter a mount code, and look good when link-previewed on Reddit/Twitter/Discord.

## Implementation
- Landing page at relay root (`/`) with:
  - Project name, one-line description, and a brief "how it works" section
  - Mount code input form that redirects to `/m/{code}/`
  - Link to GitHub repo ("View Source" / "Star on GitHub")
  - Optional: link to a read-only demo mount with sample files
- OpenGraph and Twitter Card meta tags (`og:title`, `og:description`, `og:image`) so link previews look good on social platforms
- Social preview image (simple screenshot or branded graphic)
- Mobile-responsive design consistent with the existing SPA aesthetic

## Scope
Small — 2-3 hours. Jinja2 template + meta tags + form + basic styling.

## Monetization
Free tier. Essential for discoverability and first impressions.
