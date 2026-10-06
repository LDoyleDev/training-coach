"""PostToolUse hook for Edit/Write/MultiEdit: format the file Claude just changed.

backend/**/*.py -> ruff check --fix + ruff format; frontend files -> prettier.
Formatting never blocks: if a tool is missing (e.g. before `make setup`), the hook exits 0
and `make check` still catches it. Standard library only.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PRETTIER_SUFFIXES = {".ts", ".tsx", ".js", ".css", ".json", ".html", ".md"}


def commands_for(path: Path, root: Path) -> list[list[str]]:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return []
    parts = rel.parts
    uv, npx = shutil.which("uv"), shutil.which("npx")  # full paths: npx is npx.cmd on Windows
    if parts[:1] == ("backend",) and rel.suffix == ".py" and uv:
        target = Path(*parts[1:]).as_posix()
        return [
            [uv, "run", "--quiet", "--directory", "backend", "ruff", "check", "--fix", target],
            [uv, "run", "--quiet", "--directory", "backend", "ruff", "format", target],
        ]
    prettier = root / "frontend" / "node_modules" / ".bin" / "prettier"
    if parts[:1] == ("frontend",) and rel.suffix in PRETTIER_SUFFIXES and npx and prettier.exists():
        return [[npx, "--prefix", "frontend", "prettier", "--write", rel.as_posix()]]
    return []


def main() -> int:
    event = json.load(sys.stdin)
    file_path = event.get("tool_input", {}).get("file_path")
    if not file_path:
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    for argv in commands_for(Path(file_path), root):
        # Lint findings that --fix cannot resolve are left for `make check`.
        try:
            subprocess.run(argv, cwd=root, capture_output=True, check=False, timeout=60)  # noqa: S603
        except (OSError, subprocess.TimeoutExpired):
            return 0  # tool present but unusable (blocked, hung): never block the edit
    return 0


if __name__ == "__main__":
    sys.exit(main())
