"""Tests for proxy header configuration in the relay CLI.

Verifies that uvicorn.run is called with proxy_headers=True and
forwarded_allow_ips="*" so that X-Forwarded-Proto is trusted by Starlette.
"""

from unittest.mock import MagicMock

import pytest


def test_proxy_headers_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    """uvicorn.run receives proxy_headers=True and forwarded_allow_ips='*'."""
    mock_run = MagicMock()
    monkeypatch.setattr("uvicorn.run", mock_run)
    # Ensure PORT and RELAY_ENV are set to avoid side effects
    monkeypatch.setenv("PORT", "8001")
    monkeypatch.setenv("RELAY_ENV", "development")
    # Clear sys.argv to avoid argparse picking up pytest arguments
    monkeypatch.setattr("sys.argv", ["relay"])

    from relay.cli import main

    main()

    mock_run.assert_called_once()
    call_kwargs = mock_run.call_args
    # Check keyword arguments
    assert call_kwargs.kwargs.get("proxy_headers") is True or call_kwargs[1].get("proxy_headers") is True
    assert call_kwargs.kwargs.get("forwarded_allow_ips") == "*" or call_kwargs[1].get("forwarded_allow_ips") == "*"
