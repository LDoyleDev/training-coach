"""The Claude Code hooks in .claude/hooks/ enforce CLAUDE.md rules; test them like code."""

import importlib.util
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
ROOT = HOOKS.parents[1]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load("guard_protected_files")
fmt = _load("format_edited_file")


@pytest.mark.parametrize(
    ("path", "blocked"),
    [
        ("CHANGELOG.md", True),
        (".env", True),
        (".env.production", True),
        (".env.example", False),
        ("backend/src/training_coach/config.py", False),
        ("docs/CHANGELOG-notes.md", False),
    ],
)
def test_guard_blocks_generated_and_secret_files(path: str, blocked: bool) -> None:
    assert (guard.reason_to_block(PurePosixPath(path), ROOT) is not None) is blocked


@pytest.mark.parametrize("on_main", [True, False])
def test_guard_blocks_only_applied_migrations(
    on_main: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard, "_on_main", lambda _path, _root: on_main)
    reason = guard.reason_to_block(PurePosixPath("backend/migrations/versions/x_add.py"), ROOT)
    assert (reason is not None) is on_main


def test_format_hook_picks_tool_by_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmt.shutil, "which", lambda name: f"/bin/{name}")
    backend = fmt.commands_for(ROOT / "backend" / "src" / "training_coach" / "config.py", ROOT)
    assert [argv[6] for argv in backend] == ["check", "format"]
    assert backend[0][-1] == "src/training_coach/config.py"
    assert fmt.commands_for(ROOT / "docs" / "architecture.md", ROOT) == []
    assert fmt.commands_for(Path("/elsewhere/file.py"), ROOT) == []


def test_format_hook_skips_when_tools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmt.shutil, "which", lambda _name: None)
    assert fmt.commands_for(ROOT / "backend" / "src" / "training_coach" / "config.py", ROOT) == []
