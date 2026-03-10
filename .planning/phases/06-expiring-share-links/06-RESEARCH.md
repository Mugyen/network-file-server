# Phase 6: Expiring Share Links - Research

**Researched:** 2026-03-10
**Domain:** Signed token-based file sharing with time-limited access
**Confidence:** HIGH

## Summary

Phase 6 adds the ability for users to generate expiring share links for individual files, allowing recipients to download without server authentication. The core mechanism reuses the existing `itsdangerous.URLSafeTimedSerializer` from Phase 5 with a different salt and `max_age` enforcement at validation time. An in-memory registry (Python dict) tracks active tokens for listing and revocation by the server operator.

The implementation spans three layers: (1) a backend share service and router (`/share/{token}` and `/api/shares/*`), (2) a server-rendered HTML download page for share link recipients (no React dependency), and (3) React UI additions for creating share links (ShareDialog in FileRow) and managing active links (ShareLinksPanel). The download page decision -- standalone HTML, not part of the SPA -- is critical because share link recipients may be on devices that haven't loaded the React bundle.

**Primary recommendation:** Build a `ShareLinkService` following the existing singleton pattern (`get_share_service`/`set_share_service`), use `URLSafeTimedSerializer.dumps` with a `"share-link"` salt for token creation and `.loads(token, max_age=ttl_seconds, salt="share-link")` for validation, and serve download pages via Jinja2 templates.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- "Share" action on each file row (context menu or action button) -- consistent with existing rename/delete actions in FileRow
- TTL picker as a dropdown/select with 4 fixed options: 15min, 1hr, 6hr, 24hr -- no custom input
- After creation, show the share URL in a modal/popover with a "Copy" button -- one-click copy to clipboard
- Share action available on files only, not folders (keep scope tight -- folder sharing is v2+)
- Clean, centered layout similar to DropBoxPage from Phase 5 -- file name, file size, and prominent download button
- Show file icon/type indicator for visual context
- No server branding beyond "WiFi File Server" -- recipient doesn't see folder path or host details
- Expired link page: clear "This link has expired" message with no retry option -- link is gone
- Download page is a standalone route, not part of the SPA -- works without React bundle for lightweight access
- Active links panel accessible from server UI header or a dedicated section -- server operator only
- Table/list showing: file name, creation time, expiry time, remaining TTL, share URL
- Revoke action per link -- immediate invalidation
- No bulk revoke needed for v1.1 -- single link revoke is sufficient
- Reuse itsdangerous `URLSafeTimedSerializer` from Phase 5 auth service -- same pattern, different salt
- Token encodes: file path + creation timestamp; TTL enforced at validation time via itsdangerous max_age
- In-memory registry (dict) of active tokens for listing/revocation -- tokens are ephemeral (cleared on server restart, which is a feature per REQUIREMENTS.md Out of Scope)
- Share URL format: `/share/{token}` -- clean path, token is the auth (SHARE-05)
- Share endpoint bypasses auth middleware -- the token IS the authentication

### Claude's Discretion
- Exact modal/popover design for share URL display after creation
- Share button icon and placement within FileRow
- Download page styling details (dark mode support, responsive layout)
- Active links panel location and toggle mechanism
- Error handling for share links pointing to deleted/moved files
- TTL display format (relative "expires in 45min" vs absolute "expires at 3:45 PM")

### Deferred Ideas (OUT OF SCOPE)
- Folder sharing (share entire directories as zip) -- v2+
- Max download count per link (SHARE-08) -- deferred to v2+ per REQUIREMENTS.md
- Password-protected share links (SHARE-09) -- deferred to v2+ per REQUIREMENTS.md
- Share link analytics (view count, download count) -- v2+
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SHARE-01 | User can generate an expiring share link for any file via a "Share" action | ShareLinkService.create_link() + ShareDialog component in FileRow actions |
| SHARE-02 | User can select a TTL when creating a share link (15min, 1hr, 6hr, 24hr) | ShareTTL enum with 4 values, TTL dropdown in ShareDialog, max_age enforcement |
| SHARE-03 | Link recipient sees a clean download page with file name, size, and download button | Server-rendered Jinja2 template at `/share/{token}`, standalone HTML page |
| SHARE-04 | Link recipient sees a clear "link expired" page when accessing an expired link | SignatureExpired exception handling returns expired template |
| SHARE-05 | Share links bypass password protection (the token is the authentication) | Add `/share` to auth middleware EXEMPT_PREFIXES |
| SHARE-06 | Server operator can list all active share links | In-memory registry dict + GET /api/shares endpoint + ShareLinksPanel React component |
| SHARE-07 | Server operator can revoke any active share link | DELETE /api/shares/{token} endpoint + revoke button in ShareLinksPanel |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| itsdangerous | >=2.2.0 | Token signing with TTL via `URLSafeTimedSerializer` | Already in project, `loads(max_age=N)` enforces expiry natively |
| FastAPI | >=0.115.0 | Share router endpoints (`/api/shares/*`) | Already the project framework |
| Jinja2 | (bundled with FastAPI/Starlette) | Server-rendered download/expired pages | No extra dependency; Starlette includes Jinja2Templates |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | (already installed) | Share icon for FileRow action button | `Share2` or `Link` icon from lucide |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jinja2 templates | Raw HTML string in Python | Templates are cleaner, support dark mode CSS, and match existing `templates/` dir |
| In-memory dict | SQLite/file persistence | Out of scope per REQUIREMENTS.md -- in-memory is a feature (no stale links after restart) |

**Installation:**
No new dependencies needed. `itsdangerous` and `Jinja2` (via Starlette) are already available.

## Architecture Patterns

### Recommended Project Structure
```
server/app/
├── services/
│   └── share_service.py       # ShareLinkService + get/set singleton
├── routers/
│   └── share.py               # /share/{token} (HTML) + /api/shares (JSON API)
├── models/
│   └── enums.py               # Add ShareTTL enum
│   └── schemas.py             # Add ShareLinkInfo, CreateShareRequest schemas
templates/
├── share_download.html        # Download page template
├── share_expired.html         # Expired link template
client/src/
├── components/
│   ├── ShareDialog.tsx         # Modal with TTL picker + copy URL
│   └── ShareLinksPanel.tsx     # Active links management panel
├── api/
│   └── shares.ts              # API client for share endpoints
```

### Pattern 1: ShareLinkService with In-Memory Registry
**What:** A service class that creates signed tokens, validates them, and maintains a dict of active share links for listing/revocation.
**When to use:** For all share link operations.
**Example:**
```python
# Source: Existing AuthTokenService pattern + itsdangerous docs
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from enum import Enum

class ShareTTL(int, Enum):
    FIFTEEN_MINUTES = 900
    ONE_HOUR = 3600
    SIX_HOURS = 21600
    TWENTY_FOUR_HOURS = 86400

class ShareLinkService:
    SALT = "share-link"

    def __init__(self, secret_key: str) -> None:
        self._serializer = URLSafeTimedSerializer(secret_key)
        # token -> ShareLinkRecord (file_path, created_at, ttl_seconds)
        self._active_links: dict[str, ShareLinkRecord] = {}

    def create_link(self, file_path: str, ttl: ShareTTL) -> str:
        """Create a signed share token encoding the file path."""
        token = self._serializer.dumps(
            {"path": file_path},
            salt=self.SALT,
        )
        # Register in active links
        self._active_links[token] = ShareLinkRecord(
            file_path=file_path,
            created_at=datetime.now(timezone.utc),
            ttl_seconds=ttl.value,
            token=token,
        )
        return token

    def validate_token(self, token: str) -> str:
        """Validate token and return file path. Raises on invalid/expired."""
        if token not in self._active_links:
            raise ShareLinkRevokedError(token)
        record = self._active_links[token]
        # itsdangerous enforces TTL via max_age
        data = self._serializer.loads(
            token,
            max_age=record.ttl_seconds,
            salt=self.SALT,
        )
        return data["path"]

    def revoke_link(self, token: str) -> None:
        """Remove a token from active links. Raises KeyError if not found."""
        if token not in self._active_links:
            raise ShareLinkNotFoundError(token)
        del self._active_links[token]

    def list_active_links(self) -> list[ShareLinkRecord]:
        """Return all non-expired active links."""
        # Filter out naturally expired links during listing
        ...
```

### Pattern 2: Auth Middleware Bypass for Share Routes
**What:** Add `/share` to `EXEMPT_PREFIXES` in auth_middleware.py so share links work without session cookies.
**When to use:** SHARE-05 requirement.
**Example:**
```python
# In auth_middleware.py
EXEMPT_PREFIXES = ("/api/auth/login", "/api/server-info", "/assets", "/share")
```

### Pattern 3: Server-Rendered Download Page (Not SPA)
**What:** Use Jinja2Templates from Starlette to render the download page as standalone HTML. This avoids requiring the React bundle for share link recipients.
**When to use:** SHARE-03, SHARE-04 requirements.
**Example:**
```python
# In routers/share.py
from starlette.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@router.get("/share/{token}")
def share_download_page(request: Request, token: str):
    try:
        file_path = share_service.validate_token(token)
        # Resolve file info (name, size)
        ...
        return templates.TemplateResponse("share_download.html", {
            "request": request,
            "file_name": file_name,
            "file_size": file_size_display,
            "download_url": f"/share/{token}/download",
        })
    except SignatureExpired:
        return templates.TemplateResponse("share_expired.html", {
            "request": request,
        })
```

### Pattern 4: Singleton Service Initialization
**What:** Follow existing `get_token_service`/`set_token_service` module-level singleton pattern.
**When to use:** ShareLinkService initialization in main.py / cli.py startup.
**Example:**
```python
# In share_service.py (bottom of module)
_share_service: ShareLinkService | None = None

def get_share_service() -> ShareLinkService:
    if _share_service is None:
        raise RuntimeError("ShareLinkService not initialized")
    return _share_service

def set_share_service(service: ShareLinkService) -> None:
    global _share_service
    _share_service = service
```

### Anti-Patterns to Avoid
- **Encoding TTL in the token payload:** Don't store TTL inside the signed data. The `max_age` parameter on `loads()` is the correct enforcement mechanism, and the registry stores the TTL for each token.
- **Using the same salt as auth tokens:** Share tokens and session tokens MUST use different salts to prevent cross-use attacks.
- **Serving download page through SPA routing:** The download page must work without loading the React bundle -- recipients haven't visited the server before.
- **Storing absolute file system paths in tokens:** Store the relative path (same as used in `/api/files/download?path=...`), not the resolved absolute path. This keeps tokens portable if `shared_folder` changes between server restarts (though tokens are ephemeral anyway).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token signing/expiry | Custom JWT or hash-based tokens | `itsdangerous.URLSafeTimedSerializer` with `max_age` | Handles signing, serialization, timestamp embedding, and expiry validation in one call |
| Path traversal protection | Custom path validation | Existing `resolve_safe_path()` from file_service.py | Already handles symlinks, `..` traversal, and base directory escaping |
| File download response | Custom streaming code | Existing `download_file()` + `FileResponse` pattern from files.py | Already handles Content-Disposition, UTF-8 encoding, MIME types |
| Clipboard copy | Custom clipboard API wrapper | `navigator.clipboard.writeText()` | Standard browser API, widely supported |

**Key insight:** Almost all backend infrastructure exists. The share feature is a new access path (token-based instead of session-based) to existing file download functionality.

## Common Pitfalls

### Pitfall 1: Token Validation Without Registry Check
**What goes wrong:** A revoked token still validates via `itsdangerous` because the signature is valid and not expired. Revocation only works if the registry is checked BEFORE cryptographic validation.
**Why it happens:** `itsdangerous` has no concept of revocation -- it only checks signature and age.
**How to avoid:** Always check `token in self._active_links` before calling `self._serializer.loads()`.
**Warning signs:** Revoked links still allow downloads.

### Pitfall 2: SPA Catch-All Swallowing Share Routes
**What goes wrong:** The `/{path:path}` catch-all route in `main.py` intercepts `/share/{token}` before the share router handles it, serving `index.html` instead of the download page.
**Why it happens:** FastAPI route ordering matters. The catch-all is mounted last via `app.get("/{path:path}")`, but the share router must be included before the catch-all is defined.
**How to avoid:** Include the share router in `create_app()` BEFORE the SPA catch-all mount. The current code mounts catch-all at the very end, so including the share router with `application.include_router()` before that block is sufficient.
**Warning signs:** Navigating to `/share/...` shows the SPA loading screen instead of the download page.

### Pitfall 3: Expired Links Still in Registry
**What goes wrong:** The active links registry grows without bound because expired links are never cleaned up -- they just fail validation.
**Why it happens:** Tokens expire via `max_age` but remain in the dict forever.
**How to avoid:** Lazy cleanup during `list_active_links()` -- filter out expired entries and remove them from the dict. Also clean up during `validate_token()` when `SignatureExpired` is caught.
**Warning signs:** Active links panel shows expired links.

### Pitfall 4: File Deleted After Share Link Created
**What goes wrong:** A share link points to a file that was deleted or moved after the link was created. The download fails with an unhelpful error.
**Why it happens:** The registry stores the path at creation time, but the file can change on disk.
**How to avoid:** In the download endpoint, catch `FileNotFoundError` from `download_file()` and return a "File no longer available" page. This is a Claude's Discretion item.
**Warning signs:** 500 error or Python traceback instead of a friendly error page.

### Pitfall 5: Jinja2 Template Directory Resolution
**What goes wrong:** `Jinja2Templates(directory="templates")` resolves relative to CWD, not the project root, so templates aren't found when the server is launched from a different directory.
**Why it happens:** Relative path in `Jinja2Templates` constructor.
**How to avoid:** Use the same `project_root` pattern from `main.py`: `Path(__file__).resolve().parent.parent.parent / "templates"`.
**Warning signs:** `TemplateNotFound` error when accessing share links.

## Code Examples

### itsdangerous URLSafeTimedSerializer with salt and max_age
```python
# Source: Verified against itsdangerous API (loads signature confirmed)
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

serializer = URLSafeTimedSerializer("secret-key")

# Create token with salt
token = serializer.dumps({"path": "photos/cat.jpg"}, salt="share-link")

# Validate with max_age (seconds) -- raises SignatureExpired if too old
try:
    data = serializer.loads(token, max_age=3600, salt="share-link")
    file_path = data["path"]  # "photos/cat.jpg"
except SignatureExpired:
    # Token has expired
    pass
except BadSignature:
    # Token was tampered with or wrong salt
    pass
```

### Starlette Jinja2Templates usage
```python
# Source: Starlette/FastAPI docs
from pathlib import Path
from starlette.templating import Jinja2Templates
from fastapi import Request

project_root = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(project_root / "templates"))

@router.get("/share/{token}")
def share_page(request: Request, token: str):
    return templates.TemplateResponse("share_download.html", {
        "request": request,
        "file_name": "cat.jpg",
        "file_size": "2.4 MB",
        "download_url": f"/share/{token}/download",
    })
```

### navigator.clipboard.writeText for copy-to-clipboard
```typescript
// Source: MDN Web API
async function copyToClipboard(text: string): Promise<void> {
    await navigator.clipboard.writeText(text);
}
```

### Adding share action to FileRow
```typescript
// Pattern: Add Share2 icon button alongside Download, Pencil, Trash2
import { Share2 } from "lucide-react";

// In FileRow actions div, for files only (not directories):
{!isDirectory && (
  <button
    type="button"
    onClick={handleShareClick}
    className="p-1 text-gray-400 hover:text-blue-600 ..."
    title="Share"
  >
    <Share2 className="h-4 w-4" />
  </button>
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JWT tokens for share links | `itsdangerous` signed tokens | N/A (project decision) | Simpler, no JWT dependency, built-in TTL |
| Database-backed link storage | In-memory dict | N/A (project decision) | No persistence dependency, ephemeral by design |
| SPA-based download page | Server-rendered HTML | N/A (project decision) | Works without React bundle for recipients |

## Open Questions

1. **Should the share service reuse the same secret key as the auth token service?**
   - What we know: Both use `URLSafeTimedSerializer`. The salt differentiates them cryptographically.
   - What's unclear: Whether sharing the secret key creates any security concern.
   - Recommendation: Reuse the same secret key (from `AuthTokenService`) since the salt separation prevents cross-use. This avoids managing two secret keys. If no auth service exists (no password set), generate a standalone secret key for shares.

2. **Should share links work in receive-only mode?**
   - What we know: Receive mode shows upload-only UI. Sharing implies the operator wants to distribute files.
   - What's unclear: CONTEXT.md doesn't address mode interactions.
   - Recommendation: Share link creation requires full access (not available in receive mode), but existing share links should remain downloadable in any mode since the download page is standalone.

3. **Template file naming in existing templates/ directory**
   - What we know: `templates/index.html` already exists (legacy Jinja template from original server).
   - What's unclear: Whether new templates should coexist or use a subdirectory.
   - Recommendation: Add `share_download.html` and `share_expired.html` directly in `templates/` alongside `index.html`. No subdirectory needed for 2 files.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio 0.25+ |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest server/tests/test_share.py -x` |
| Full suite command | `uv run pytest server/tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SHARE-01 | Create share link for a file via API | unit + integration | `uv run pytest server/tests/test_share.py::test_create_share_link -x` | No -- Wave 0 |
| SHARE-02 | TTL selection (4 options) and enforcement | unit | `uv run pytest server/tests/test_share_service.py::test_ttl_values -x` | No -- Wave 0 |
| SHARE-03 | Download page renders file info | integration | `uv run pytest server/tests/test_share.py::test_download_page_renders -x` | No -- Wave 0 |
| SHARE-04 | Expired link shows expired page | integration | `uv run pytest server/tests/test_share.py::test_expired_link -x` | No -- Wave 0 |
| SHARE-05 | Share links bypass auth middleware | integration | `uv run pytest server/tests/test_share.py::test_share_bypasses_auth -x` | No -- Wave 0 |
| SHARE-06 | List active share links | unit + integration | `uv run pytest server/tests/test_share.py::test_list_active_links -x` | No -- Wave 0 |
| SHARE-07 | Revoke a share link | unit + integration | `uv run pytest server/tests/test_share.py::test_revoke_link -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest server/tests/test_share.py -x`
- **Per wave merge:** `uv run pytest server/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `server/tests/test_share_service.py` -- unit tests for ShareLinkService (create, validate, revoke, expiry, cleanup)
- [ ] `server/tests/test_share.py` -- integration tests for share router endpoints (create link, download page, expired page, auth bypass, list, revoke)
- [ ] Share service fixture in `server/tests/conftest.py` -- `configured_app_with_shares` fixture providing a ShareLinkService

## Sources

### Primary (HIGH confidence)
- Project codebase: `server/app/services/auth_service.py` -- existing `URLSafeTimedSerializer` pattern
- Project codebase: `server/app/middleware/auth_middleware.py` -- EXEMPT_PREFIXES mechanism
- Project codebase: `server/app/main.py` -- router inclusion order and SPA catch-all
- itsdangerous API: `URLSafeTimedSerializer.loads(s, max_age, salt)` -- verified via Python help()
- Project codebase: `server/app/services/file_service.py` -- `download_file()` and `resolve_safe_path()`

### Secondary (MEDIUM confidence)
- Starlette docs: `Jinja2Templates` class and `TemplateResponse` usage

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, no new dependencies
- Architecture: HIGH -- follows established patterns (singleton services, router modules, ASGI middleware exemptions)
- Pitfalls: HIGH -- identified from direct code analysis (SPA catch-all ordering, template path resolution, registry cleanup)

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no external dependencies changing)
