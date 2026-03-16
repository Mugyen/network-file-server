"""Tests for the landing page router and Jinja2 error templates."""

import pytest

from relay.app.routers.landing import templates


# ---------------------------------------------------------------------------
# GET / — landing page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_landing_page_returns_200(relay_client) -> None:
    response = await relay_client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_landing_page_contains_wifi_file_server(relay_client) -> None:
    response = await relay_client.get("/")
    assert "WiFi File Server" in response.text


@pytest.mark.asyncio
async def test_landing_page_contains_code_input_form(relay_client) -> None:
    response = await relay_client.get("/")
    # Must contain a form with a text input named "code"
    assert '<input' in response.text
    assert 'name="code"' in response.text


# ---------------------------------------------------------------------------
# GET /?code=XXX — redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_code_redirect_returns_302(relay_client) -> None:
    response = await relay_client.get("/?code=abc123", follow_redirects=False)
    assert response.status_code == 302


@pytest.mark.asyncio
async def test_code_redirect_location_header(relay_client) -> None:
    response = await relay_client.get("/?code=abc123", follow_redirects=False)
    assert response.headers["location"] == "/m/abc123/"


@pytest.mark.asyncio
async def test_code_redirect_alphanumeric(relay_client) -> None:
    response = await relay_client.get("/?code=ABCD1234", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/m/ABCD1234/"


# ---------------------------------------------------------------------------
# GET /?code= (empty) — no redirect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_code_returns_landing_page(relay_client) -> None:
    response = await relay_client.get("/?code=", follow_redirects=False)
    assert response.status_code == 200
    assert "WiFi File Server" in response.text


# ---------------------------------------------------------------------------
# Template smoke tests — render without errors
# ---------------------------------------------------------------------------


def test_not_found_template_renders() -> None:
    tmpl = templates.get_template("not_found.html")
    rendered = tmpl.render({})
    assert "Mount Not Found" in rendered


def test_not_found_template_contains_code_input() -> None:
    tmpl = templates.get_template("not_found.html")
    rendered = tmpl.render({})
    assert '<input' in rendered
    assert 'name="code"' in rendered


def test_offline_template_renders() -> None:
    tmpl = templates.get_template("offline.html")
    rendered = tmpl.render({})
    assert "offline" in rendered.lower()


def test_expired_template_renders() -> None:
    tmpl = templates.get_template("expired.html")
    rendered = tmpl.render({})
    assert "expired" in rendered.lower()


def test_landing_template_renders() -> None:
    tmpl = templates.get_template("landing.html")
    rendered = tmpl.render({})
    assert "WiFi File Server" in rendered


def test_all_error_templates_extend_base() -> None:
    """Verify error templates include the card container from base.html."""
    for name in ("not_found.html", "offline.html", "expired.html"):
        tmpl = templates.get_template(name)
        rendered = tmpl.render({})
        # base.html provides the .card container
        assert "card" in rendered, f"{name} should inherit .card from base.html"
