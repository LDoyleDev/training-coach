"""CLAUDE.md: domain/ is pure logic. Fail if it imports frameworks or I/O libraries."""

import ast
from pathlib import Path

import pytest

DOMAIN = Path(__file__).resolve().parents[2] / "src" / "training_coach" / "domain"
FORBIDDEN = {
    "sqlalchemy",
    "alembic",
    "fastapi",
    "starlette",
    "telegram",
    "httpx",
    "requests",
    "structlog",
    "pydantic",
    "os",
    "subprocess",
    "socket",
    "training_coach.db",
    "training_coach.services",
    "training_coach.api",
    "training_coach.bot",
    "training_coach.config",
}


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", sorted(DOMAIN.glob("*.py")), ids=lambda p: p.name)
def test_domain_module_is_pure(path: Path) -> None:
    bad = {
        name
        for name in _imports(path)
        if any(name == f or name.startswith(f + ".") for f in FORBIDDEN)
    }
    assert not bad, f"{path.name} imports {sorted(bad)}"
