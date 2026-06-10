"""Tests for relay.app.services.html_rewriter — rewrite + hardening."""

from relay.app.services.html_rewriter import (
    HTML_REWRITE_MAX_BYTES,
    charset_from_content_type,
    rewrite_html_asset_paths,
    rewrite_html_body,
)


class TestRewriteHtmlAssetPaths:
    """Unit tests for HTML asset path rewriting (moved from mount proxy)."""

    def test_rewrites_script_src(self) -> None:
        html = '<script src="/assets/index-abc.js"></script>'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<script src="/m/CODE1/assets/index-abc.js"></script>'

    def test_rewrites_link_href(self) -> None:
        html = '<link rel="stylesheet" href="/assets/index-xyz.css">'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<link rel="stylesheet" href="/m/CODE1/assets/index-xyz.css">'

    def test_rewrites_favicon(self) -> None:
        html = '<link rel="icon" href="/favicon.ico">'
        result = rewrite_html_asset_paths(html, "/m/CODE1")
        assert result == '<link rel="icon" href="/m/CODE1/favicon.ico">'

    def test_does_not_double_rewrite(self) -> None:
        html = '<script src="/m/CODE1/assets/index.js"></script>'
        assert rewrite_html_asset_paths(html, "/m/CODE1") == html

    def test_rewrites_single_quoted_attributes(self) -> None:
        html = "<script src='/assets/app.js'></script>"
        result = rewrite_html_asset_paths(html, "/m/XYZ")
        assert result == "<script src='/m/XYZ/assets/app.js'></script>"

    def test_full_index_html(self) -> None:
        html = (
            '<!doctype html><html><head>'
            '<script type="module" src="/assets/index-C4XEGJkC.js"></script>'
            '<link rel="stylesheet" href="/assets/index-BZCOt5Ge.css">'
            '</head><body><div id="root"></div></body></html>'
        )
        result = rewrite_html_asset_paths(html, "/m/t7F5Twps")
        assert '"/m/t7F5Twps/assets/index-C4XEGJkC.js"' in result
        assert '"/m/t7F5Twps/assets/index-BZCOt5Ge.css"' in result

    def test_preserves_non_asset_content(self) -> None:
        html = '<div data-path="/some/thing">text</div>'
        assert rewrite_html_asset_paths(html, "/m/CODE") == html


class TestCharsetDetection:
    def test_default_is_utf8(self) -> None:
        assert charset_from_content_type("text/html") == "utf-8"

    def test_explicit_charset(self) -> None:
        assert charset_from_content_type("text/html; charset=ISO-8859-1") == "iso-8859-1"

    def test_quoted_charset(self) -> None:
        assert charset_from_content_type('text/html; charset="utf-8"') == "utf-8"


class TestRewriteHtmlBodyHardening:
    def test_rewrites_utf8_body(self) -> None:
        body = '<script src="/assets/a.js"></script>'.encode("utf-8")
        out = rewrite_html_body(body, "text/html; charset=utf-8", "/m/C")
        assert b"/m/C/assets/a.js" in out

    def test_rewrites_latin1_body(self) -> None:
        body = '<a href="/f.bin">caf\xe9</a>'.encode("iso-8859-1")
        out = rewrite_html_body(body, "text/html; charset=iso-8859-1", "/m/C")
        assert b'href="/m/C/f.bin"' in out
        assert "café".encode("iso-8859-1") in out

    def test_undecodable_body_passes_through(self) -> None:
        body = b"\xff\xfe\x00\x01 not utf-8 at all \x80"
        assert rewrite_html_body(body, "text/html; charset=utf-8", "/m/C") == body

    def test_unknown_charset_passes_through(self) -> None:
        body = b'<a href="/x">x</a>'
        assert rewrite_html_body(body, "text/html; charset=klingon-8", "/m/C") == body

    def test_oversized_body_passes_through(self) -> None:
        body = b"x" * (HTML_REWRITE_MAX_BYTES + 1)
        assert rewrite_html_body(body, "text/html", "/m/C") is body
