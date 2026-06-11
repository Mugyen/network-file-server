"""Import-direction guards — keep the package graph acyclic and the
boundaries honest (review items C2–C4).

Rules enforced (application code only; tests are exempt):
- server/  must never import relay or agent (no cycle, no upward dependency)
- agent/   must never import server (it tunnels *any* ASGI app; the
           composition root is server/app/bootstrap.py)
- relay/   may depend on server, but only through the declared public
           interface (``from server import ...``), never server.app.* internals
- tunnel/, accounts/, shared/ must not import any other project package
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROJECT_PACKAGES = {"server", "relay", "agent", "tunnel", "accounts", "shared"}


def _imports_of(package_dir: Path) -> list[tuple[str, str]]:
    """Return (file, imported_module) for every import in a package's .py files."""
    found: list[tuple[str, str]] = []
    for py in sorted(package_dir.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        rel = str(py.relative_to(REPO_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                found.append((rel, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    found.append((rel, alias.name))
    return found


def _violations(package: str, predicate) -> list[str]:
    return [
        f"{file}: {module}"
        for file, module in _imports_of(REPO_ROOT / package)
        if predicate(module)
    ]


# The CLI is the deliberate composition root: it joins server and agent
# (builds the app factory and hands it to the agent). It is the ONLY
# server file allowed to import agent.
COMPOSITION_ROOT = "server/app/bootstrap.py"


def test_server_does_not_import_relay() -> None:
    bad = _violations("server", lambda m: m.split(".")[0] == "relay")
    assert bad == [], f"server must not depend on relay: {bad}"


def test_server_imports_agent_only_in_composition_root() -> None:
    bad = [
        v
        for v in _violations("server", lambda m: m.split(".")[0] == "agent")
        if not v.startswith(COMPOSITION_ROOT)
    ]
    assert bad == [], (
        f"only the composition root ({COMPOSITION_ROOT}) may import agent: {bad}"
    )


def test_agent_does_not_import_server() -> None:
    bad = _violations("agent", lambda m: m.split(".")[0] == "server")
    assert bad == [], (
        f"agent must not depend on server (app factory is injected): {bad}"
    )


def test_relay_imports_server_only_via_public_interface() -> None:
    bad = _violations(
        "relay",
        lambda m: m == "server.app" or m.startswith("server.app."),
    )
    assert bad == [], (
        f"relay must import only the server package root (`from server import ...`), "
        f"not internals: {bad}"
    )


def test_leaf_packages_are_self_contained() -> None:
    for leaf in ("tunnel", "accounts", "shared"):
        others = PROJECT_PACKAGES - {leaf}
        bad = _violations(leaf, lambda m: m.split(".")[0] in others)
        assert bad == [], f"{leaf} must not depend on other project packages: {bad}"
