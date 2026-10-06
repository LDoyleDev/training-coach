"""The Claude Code hooks in .claude/hooks/ enforce CLAUDE.md rules; test them like code."""

import importlib.util
import io
import json
import subprocess
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


@pytest.mark.parametrize(
    ("event", "script"),
    [("PreToolUse", "guard_protected_files.py"), ("PostToolUse", "format_edited_file.py")],
)
def test_hooks_are_registered(event: str, script: str) -> None:
    """A hook file that settings.json doesn't register enforces nothing."""
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text())
    entries = settings["hooks"][event]
    commands = [h["command"] for e in entries if "Edit" in e["matcher"] for h in e["hooks"]]
    assert any(script in command for command in commands)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo with one applied migration on origin/main."""
    (tmp_path / "backend/migrations/versions").mkdir(parents=True)
    (tmp_path / "backend/migrations/versions/a_applied.py").write_text("x = 1\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


@pytest.mark.parametrize(("name", "blocked"), [("a_applied.py", True), ("b_new.py", False)])
def test_guard_checks_migrations_against_real_git(repo: Path, name: str, blocked: bool) -> None:
    path = PurePosixPath(f"backend/migrations/versions/{name}")
    assert (guard.reason_to_block(path, repo) is not None) is blocked


def test_guard_fails_closed_without_origin_main(repo: Path) -> None:
    """A fresh or single-branch clone has no origin/main; block rather than guess."""
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    reason = guard.reason_to_block(PurePosixPath("backend/migrations/versions/b_new.py"), repo)
    assert reason is not None
    assert "git fetch origin main" in reason


def test_format_hook_picks_tool_by_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmt.shutil, "which", lambda name: f"/bin/{name}")
    backend = fmt.commands_for(ROOT / "backend" / "src" / "training_coach" / "config.py", ROOT)
    assert [argv[argv.index("ruff") + 1] for argv in backend] == ["check", "format"]
    assert backend[0][-1] == "src/training_coach/config.py"
    assert fmt.commands_for(ROOT / "docs" / "architecture.md", ROOT) == []
    assert fmt.commands_for(Path("/elsewhere/file.py"), ROOT) == []


def test_format_hook_skips_when_tools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmt.shutil, "which", lambda _name: None)
    assert fmt.commands_for(ROOT / "backend" / "src" / "training_coach" / "config.py", ROOT) == []


@pytest.mark.parametrize("stdin", ["not json", "[]"])
def test_guard_fails_closed_on_bad_input(
    stdin: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 1 would let the edit through; anything unexpected must block (exit 2)."""
    monkeypatch.setattr(guard.sys, "stdin", io.StringIO(stdin))
    assert guard.main() == 2
    assert "guard hook failed" in capsys.readouterr().err
