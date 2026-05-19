"""The accounts library must stay framework-agnostic (no web deps)."""

import subprocess
import sys


def test_accounts_imports_without_fastapi():
    # Run in a clean interpreter so other tests' imports don't pollute sys.modules.
    code = (
        "import accounts, sys; "
        "assert 'fastapi' not in sys.modules, 'accounts pulled in fastapi'; "
        "assert 'starlette' not in sys.modules, 'accounts pulled in starlette'"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
