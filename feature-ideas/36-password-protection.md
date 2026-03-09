# Password Protection

## Summary
Simple password gate for the whole server. Set a password via CLI flag and anyone trying to access the web UI must enter it first. No accounts, no setup — just a single shared secret.

## Why This Matters
The most-requested feature for any sharing tool. Without it, anyone on the same network can access your files. Especially important in offices, cafes, and shared living spaces where the WiFi is shared with strangers.

## Implementation
- `--password` CLI flag sets a server-wide password
- Login page served at `/login` with a simple password form
- Session cookie set on success (short-lived, e.g. 24h)
- All API endpoints return 401 if session cookie is missing/invalid
- Password stored as bcrypt hash in memory (never on disk)
- Optional: `--password-file` to read password from a file (for scripting)
- QR code still works — scanner lands on login page first

## Scope
Small — 2-4 hours. Mostly middleware + a login page.

## Monetization
Free tier. It's a basic safety feature that should ship with the core product.
