# Dark Mode & Custom Themes

## Summary
System-aware dark mode, plus customizable themes. Let users (or the server admin) brand the interface with custom colors, logos, and layouts.

## Why This Matters
Dark mode is expected in 2026. Custom theming lets businesses brand the server (photographer's logo, company colors), making it feel professional rather than generic. Small feature, big perception shift.

## Implementation
- Dark mode with `prefers-color-scheme` media query
- Manual toggle with preference persistence (localStorage)
- CSS custom properties for all colors (easy theming)
- Built-in theme presets: Light, Dark, Nord, Solarized, High Contrast
- Custom theme editor: pick primary/secondary/accent colors
- Logo upload for branding the header
- Custom welcome message / instructions text
- Compact vs. comfortable layout density toggle
- Font size adjustment for accessibility

## Scope
Small-medium — 3-5 hours. CSS variables make this straightforward.

## Monetization
Free tier (dark mode). Pro tier: custom branding, logo, presets.
