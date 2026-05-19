# Security Hardening Audit for Public Relay

## Summary
Focused security audit and hardening pass for running the relay as a public-facing service. Covers path traversal edge cases, Content-Security-Policy headers, cookie security, and input sanitization.

## Why This Matters
The server was originally designed for trusted LAN environments. A public relay fundamentally changes the threat model — every request is potentially adversarial. Security issues that are harmless on a local network become exploitable when internet-facing.

## Implementation

### Content-Security-Policy Headers
- Add CSP headers to all relay responses: restrict script sources, style sources, frame ancestors
- Prevent XSS via script injection in filenames or clipboard content

### Cookie Security
- `Secure` flag on all cookies when served over HTTPS
- `SameSite=Strict` on relay (currently `Lax`)
- `HttpOnly` flag on session cookies (verify already set)
- Cookie path scoping audit: ensure `/m/{code}/` scoping doesn't leak

### Input Sanitization
- Fuzz-test path traversal with unicode normalization edge cases (e.g., `%2e%2e`, `..%c0%af`, NUL bytes)
- Symlink following audit: ensure `resolve()` doesn't escape the shared folder via symlinks
- Filename sanitization for display (prevent HTML injection in file listings)

### Relay-Specific
- Strip or sanitize `X-Forwarded-*` headers from browser requests before tunneling (prevent header injection)
- Validate mount codes are alphanumeric only
- Max header size and max query string length on proxy

## Scope
Medium — 4-6 hours. Audit + CSP headers + cookie hardening + fuzz testing.

## Monetization
Infrastructure. Non-negotiable before public launch.
