# PyPI Publishing

## Summary
Publish `wifi-file-server` and `wifi-relay` as installable packages on PyPI so users can install and run with a single command: `pip install wifi-file-server && wifi-file-server mount ./folder --server https://relay.example.com`.

## Why This Matters
The number one factor for Reddit/HN adoption is friction-to-try. If someone has to clone a repo, install uv, build the frontend, and run from source, 90% of potential users drop off. `pip install` is the expected distribution channel for Python CLI tools.

## Implementation
- Verify `pyproject.toml` metadata: name, version, description, author, license, homepage, repository URL
- Pre-build the React SPA and include `client/dist/` in the sdist/wheel (via `package-data` or `MANIFEST.in`)
- Ensure console script entry points (`wifi-file-server`, `wifi-relay`) work from a clean pip install
- Test installation in a clean virtualenv
- Set up GitHub Actions workflow for automated publishing on git tag (e.g., `v1.2.0`)
- Add PyPI badge to README

## Scope
Small — 2-3 hours. Metadata + build config + test install + optional CI workflow.

## Monetization
Free tier. Distribution infrastructure.
