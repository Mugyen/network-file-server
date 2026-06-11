"""Emit the server's OpenAPI schema as JSON (for client type generation).

``scripts/gen_api_types.sh`` runs this and pipes the output into
``openapi-typescript`` to regenerate ``client/src/types/api.gen.ts``. CI runs
the same pipeline and fails on any diff, so a backend schema change that is
not reflected in the client types breaks the build instead of users.

Run: ``uv run python -m server.app.openapi_dump``
"""

import json
import sys
import tempfile
from pathlib import Path

from server.app.config import create_default_config
from server.app.main import create_app


def build_openapi() -> dict:
    """Return the server app's OpenAPI schema as a dict.

    Uses a throwaway temp directory as the shared folder — the schema does
    not depend on folder contents, only on route/model declarations.
    """
    with tempfile.TemporaryDirectory() as tmp:
        config = create_default_config(shared_folder=Path(tmp), port=8000)
        app = create_app(config)
        return app.openapi()


def main() -> None:
    """Print the OpenAPI schema as formatted JSON to stdout."""
    json.dump(build_openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
