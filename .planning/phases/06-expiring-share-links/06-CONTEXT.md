# Phase 6: Expiring Share Links - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can generate temporary, self-expiring links to share specific files, and recipients can download without needing server access. Server operator can list and revoke active share links. Covers SHARE-01 through SHARE-07.

</domain>

<decisions>
## Implementation Decisions

### Share link creation UX
- "Share" action on each file row (context menu or action button) — consistent with existing rename/delete actions in FileRow
- TTL picker as a dropdown/select with 4 fixed options: 15min, 1hr, 6hr, 24hr — no custom input
- After creation, show the share URL in a modal/popover with a "Copy" button — one-click copy to clipboard
- Share action available on files only, not folders (keep scope tight — folder sharing is v2+)

### Download page design
- Clean, centered layout similar to DropBoxPage from Phase 5 — file name, file size, and prominent download button
- Show file icon/type indicator for visual context
- No server branding beyond "WiFi File Server" — recipient doesn't need to see folder path or host details
- Expired link page: clear "This link has expired" message with no retry option — link is gone
- Download page is a standalone route, not part of the SPA — works without React bundle for lightweight access

### Share link management
- Active links panel accessible from server UI header or a dedicated section — server operator only (not shown to share link recipients)
- Table/list showing: file name, creation time, expiry time, remaining TTL, share URL
- Revoke action per link — immediate invalidation
- No bulk revoke needed for v1.1 — single link revoke is sufficient

### Token strategy
- Reuse itsdangerous `URLSafeTimedSerializer` from Phase 5 auth service — same pattern, different salt
- Token encodes: file path + creation timestamp; TTL enforced at validation time via itsdangerous max_age
- In-memory registry (dict) of active tokens for listing/revocation — tokens are ephemeral (cleared on server restart, which is a feature per REQUIREMENTS.md Out of Scope)
- Share URL format: `/share/{token}` — clean path, token is the auth (SHARE-05)
- Share endpoint bypasses auth middleware — the token IS the authentication

### Claude's Discretion
- Exact modal/popover design for share URL display after creation
- Share button icon and placement within FileRow
- Download page styling details (dark mode support, responsive layout)
- Active links panel location and toggle mechanism
- Error handling for share links pointing to deleted/moved files
- TTL display format (relative "expires in 45min" vs absolute "expires at 3:45 PM")

</decisions>

<specifics>
## Specific Ideas

- Share URL should be short enough to paste in a chat message — `/share/{token}` not `/api/shares/download?token={token}&...`
- Download page should work even on devices that haven't visited the server before — no JS framework dependency for the basic download flow
- The "link expired" page should be friendly, not a raw error — similar care as the login page from Phase 5

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AuthTokenService` + `URLSafeTimedSerializer` in `auth_service.py`: Same itsdangerous pattern for signing share tokens with TTL
- `FileRow` component actions pattern: Existing rename/delete actions in FileRow provide the insertion point for a "Share" button
- `DropBoxPage` centered layout: Download page can follow the same centered, clean layout pattern
- `download_file()` in `file_service.py`: Existing file download logic for resolving paths and serving files
- `/api/files/download` endpoint in `files.py`: Existing download with path traversal protection — share endpoint reuses this logic

### Established Patterns
- Module-level singleton pattern (`get_token_service`/`set_token_service`): Share link registry can follow the same pattern
- Pure ASGI middleware with path allowlisting: Auth middleware already allowlists `/api/auth/*` — add `/share/*` to allowlist
- `ServerConfig` extension pattern: If needed, add share-related config fields using same pattern as Phase 5
- Router module pattern: New `routers/share.py` following existing router conventions

### Integration Points
- Auth middleware allowlist: `/share/*` paths must bypass authentication (SHARE-05)
- FileRow component: Add "Share" action alongside existing rename/delete actions
- `create_app()` in `main.py`: Register share router and share link service
- `/api/server-info`: Could expose whether sharing is enabled (always true for now)
- CLI startup: No new CLI flags needed — sharing is always available

</code_context>

<deferred>
## Deferred Ideas

- Folder sharing (share entire directories as zip) — v2+
- Max download count per link (SHARE-08) — deferred to v2+ per REQUIREMENTS.md
- Password-protected share links (SHARE-09) — deferred to v2+ per REQUIREMENTS.md
- Share link analytics (view count, download count) — v2+

</deferred>

---

*Phase: 06-expiring-share-links*
*Context gathered: 2026-03-10*
