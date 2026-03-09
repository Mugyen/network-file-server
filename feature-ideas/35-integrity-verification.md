# File Integrity Verification

## Summary
Automatic checksum verification for every transfer. Files are hashed before and after transfer, with mismatches flagged immediately. Optional blockchain-style verification chain for compliance use cases.

## Why This Matters
"Did the file transfer correctly?" is a question users can't currently answer. Corrupted transfers are silent failures. For legal, medical, or financial files, integrity verification isn't optional — it's required. This is a trust feature that justifies enterprise pricing.

## Implementation
- SHA-256 hash computed on upload (client-side via Web Crypto API)
- Server computes hash on receipt and compares
- Mismatch triggers automatic retry or error notification
- Hash displayed in file details (verifiable by recipient)
- Verification badge on files that pass integrity check
- Batch verify: check all files in a folder
- Export integrity report (file list + hashes) as signed document
- Optional: GPG signing for files
- Transfer receipt: downloadable proof of successful transfer with timestamp + hash
- Tamper detection: alert if a file changes after upload

## Scope
Small-medium — 3-5 hours. Web Crypto API + server-side hashing.

## Monetization
Pro tier. Compliance and trust features command premium pricing.
