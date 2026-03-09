# End-to-End Encrypted Transfers

## Summary
PIN-protected sessions and encrypted file transfers. Files are encrypted in the browser before upload and decrypted after download — the server never sees plaintext content.

## Why This Matters
"AirDrop but encrypted and cross-platform" is a compelling pitch. Privacy-conscious users, journalists, lawyers, healthcare workers — anyone handling sensitive files on shared networks. This is a strong differentiator from every free alternative.

## Implementation
- Session PIN: server generates a 4-6 digit PIN on startup, displayed in terminal
- Users must enter PIN to access the web UI
- Web Crypto API for client-side AES-256-GCM encryption
- Key derived from PIN + session salt using PBKDF2
- Files encrypted in browser before upload, decrypted in browser after download
- Server only stores/transfers encrypted blobs
- Optional: HTTPS via self-signed cert generation (mkcert integration)
- Visual indicator showing encryption status on each file

## Scope
Large — 8-12 hours. Crypto is straightforward but needs careful implementation.

## Monetization
Pro tier. This is a clear premium feature with real value.
