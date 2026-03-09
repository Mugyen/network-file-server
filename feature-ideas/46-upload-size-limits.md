# Upload Size Limits & Warnings

## Summary
Configurable maximum upload file size via a CLI flag. Warn the user in the browser before they start a large upload, and reject oversized files at the server with a clear error message.

## Why This Matters
Without limits, a guest can accidentally (or intentionally) fill your disk with a 50GB video. Even without malicious intent, large accidental uploads are a support burden. Early warnings prevent wasted time on uploads that will be rejected.

## Implementation
- `--max-upload-size` CLI flag (e.g. `--max-upload-size 500MB`), default unlimited
- `GET /api/server-info` exposes the limit so the frontend can enforce it
- Frontend: warn before upload starts if any file exceeds the limit (show size + limit in message)
- Backend: validate `Content-Length` header and reject with `413 Payload Too Large` if exceeded
- Per-file and per-batch validation
- Limit displayed in the upload drop zone ("Max file size: 500 MB")
- Optional: `--max-total-upload-size` to cap total disk usage across all uploads

## Scope
Small — 2-3 hours. CLI flag + middleware validation + frontend warning.

## Monetization
Free tier. A sensible default for shared environments.
