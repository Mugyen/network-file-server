# Desktop System Tray App

## Summary
A native desktop wrapper (Tauri or Electron) that sits in the system tray. Always running, always ready. Right-click a file in Finder/Explorer and "Share via WiFi Server." Native OS integration is the moat.

## Why This Matters
CLI tools die when the terminal closes. A tray app is persistent, discoverable, and feels like a real product. OS-level integration (context menu, drag to tray icon) creates habits that are hard to break. This is what separates a script from a product.

## Implementation
- Tauri wrapper (Rust-based, small binary, low memory)
- System tray icon with status indicator (green=running, red=stopped)
- Tray menu: start/stop server, open in browser, show QR code, settings
- OS context menu integration: right-click file -> "Share via WiFi Server"
- Drag file onto tray icon to instantly share it
- Auto-start on login (optional)
- Native notifications for uploads/downloads
- Settings GUI: port, shared folder, theme, encryption toggle
- Auto-update mechanism
- Platform-specific installers: .dmg (macOS), .msi (Windows), .AppImage (Linux)

## Scope
Large — 15-25 hours. Tauri setup, platform-specific integrations, packaging.

## Monetization
Pro tier. The desktop app IS the product for most users.
