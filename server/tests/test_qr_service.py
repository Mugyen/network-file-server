"""Tests for QR code generation service.

Tests ASCII QR (terminal) and SVG QR (web) generation.
"""

import pytest

from server.app.services.qr_service import generate_ascii_qr, generate_svg_qr


class TestAsciiQr:
    """Tests for generate_ascii_qr function."""

    def test_returns_non_empty_string(self) -> None:
        """ASCII QR output must be a non-empty string."""
        result = generate_ascii_qr("http://192.168.1.5:8000")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_output_is_multiline(self) -> None:
        """ASCII QR must contain newlines (multi-line output)."""
        result = generate_ascii_qr("http://192.168.1.5:8000")
        assert "\n" in result

    def test_empty_url_raises_value_error(self) -> None:
        """Empty URL must raise ValueError."""
        with pytest.raises(ValueError, match="url must not be empty"):
            generate_ascii_qr("")

    def test_different_urls_produce_different_output(self) -> None:
        """Different URLs produce different QR codes."""
        result_a = generate_ascii_qr("http://192.168.1.5:8000")
        result_b = generate_ascii_qr("http://10.0.0.1:3000")
        assert result_a != result_b


class TestSvgQr:
    """Tests for generate_svg_qr function."""

    def test_returns_valid_svg(self) -> None:
        """SVG QR output must start with XML/SVG declaration."""
        result = generate_svg_qr("http://192.168.1.5:8000")
        assert isinstance(result, str)
        # SVG may start with <?xml or <svg
        assert result.strip().startswith("<?xml") or result.strip().startswith("<svg")

    def test_contains_path_element(self) -> None:
        """SVG output must contain path element (the QR code drawing data)."""
        result = generate_svg_qr("http://192.168.1.5:8000")
        assert "path" in result.lower()

    def test_empty_url_raises_value_error(self) -> None:
        """Empty URL must raise ValueError."""
        with pytest.raises(ValueError, match="url must not be empty"):
            generate_svg_qr("")

    def test_different_urls_produce_different_output(self) -> None:
        """Different URLs produce different SVG QR codes."""
        result_a = generate_svg_qr("http://192.168.1.5:8000")
        result_b = generate_svg_qr("http://10.0.0.1:3000")
        assert result_a != result_b
