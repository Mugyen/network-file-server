"""HTML asset-path rewriting for proxied mounts — hardened.

The proxy rewrites absolute asset paths (``src="/assets/..."``) in HTML
responses so they resolve under the mount prefix (``/m/{code}/assets/...``).
This module makes that rewrite safe against hostile or odd content:

- Charset is taken from the Content-Type header (default utf-8); a body
  that does not decode is passed through UNMODIFIED rather than crashing
  the proxy (the rewrite is cosmetic; bytes > 500).
- Bodies above ``HTML_REWRITE_MAX_BYTES`` are never buffered for rewriting
  — callers stream them through unchanged.
"""

import re

# Rewrite is for SPA shells and small pages; anything bigger is streamed
# through unmodified instead of buffered in relay memory.
HTML_REWRITE_MAX_BYTES: int = 5 * 1024 * 1024

# Pattern matching src="/ or href="/ attribute values pointing to absolute paths.
# Captures the attribute prefix so we can rewrite only the path portion.
_ASSET_PATH_RE: re.Pattern[str] = re.compile(r'((?:src|href)=["\'])/(?!m/)')

_CHARSET_RE: re.Pattern[str] = re.compile(r"charset=([^\s;]+)", re.IGNORECASE)


def rewrite_html_asset_paths(html: str, mount_prefix: str) -> str:
    """Rewrite absolute asset paths in HTML to include the mount prefix.

    Transforms ``src="/assets/..."`` into ``src="/m/{code}/assets/..."`` (and
    likewise for ``href``). Only rewrites paths that don't already start with
    ``/m/`` to avoid double-rewriting.

    Args:
        html:         Raw HTML string from the agent response.
        mount_prefix: The mount URL prefix, e.g. ``/m/ABC123``.

    Returns:
        HTML string with asset paths rewritten to include the mount prefix.
    """
    return _ASSET_PATH_RE.sub(rf"\1{mount_prefix}/", html)


def charset_from_content_type(content_type: str) -> str:
    """Extract the charset parameter from a Content-Type value.

    Returns ``utf-8`` when no charset parameter is present.
    """
    if not isinstance(content_type, str):
        raise ValueError(f"content_type must be a string, got {type(content_type)!r}")
    match = _CHARSET_RE.search(content_type)
    if match is None:
        return "utf-8"
    return match.group(1).strip("\"'").lower()


def rewrite_html_body(body: bytes, content_type: str, mount_prefix: str) -> bytes:
    """Rewrite asset paths in an HTML body; degrade to passthrough, never crash.

    Returns the body UNMODIFIED when it exceeds HTML_REWRITE_MAX_BYTES,
    when the declared charset is unknown, or when the bytes do not decode
    with it — serving unrewritten HTML is strictly better than a 500.

    Args:
        body:         Raw response body bytes.
        content_type: Full Content-Type header value (charset detection).
        mount_prefix: The mount URL prefix, e.g. ``/m/ABC123``.
    """
    if len(body) > HTML_REWRITE_MAX_BYTES:
        return body
    charset = charset_from_content_type(content_type)
    try:
        text = body.decode(charset)
    except (UnicodeDecodeError, LookupError):
        # Mislabeled or non-text content — pass through untouched.
        return body
    return rewrite_html_asset_paths(text, mount_prefix).encode(charset)
