"""scripts/auto-deploy.sh (ADR-0030), run for real against throwaway git repos.

``docker`` and ``curl`` are stubs on PATH: docker records its calls (and can be told to fail
the backup or the rebuild), curl answers /healthz with whatever the test wrote to a file.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "auto-deploy.sh"
# Windows' bash on PATH may be WSL's. To run these natively, set TC_TEST_BASH to
# "C:/Program Files/Git/usr/bin/bash.exe" (not Git/bin/bash.exe: it puts its own curl first).
BASH = os.environ.get("TC_TEST_BASH") or (shutil.which("bash") if sys.platform != "win32" else None)

pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash (set TC_TEST_BASH on Windows)")

DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$STUB_DIR/docker.log"
case "$*" in
  *exec*backup*) [ ! -e "$STUB_DIR/fail-backup" ] && [ ! -e "$STUB_DIR/fail-exec" ] ;;
  *backup*) [ ! -e "$STUB_DIR/fail-backup" ] ;;
  *up\\ -d*) [ ! -e "$STUB_DIR/fail-up" ] ;;
esac
"""
CURL = """#!/usr/bin/env bash
cat "$STUB_DIR/health" 2>/dev/null || exit 7
"""


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


@dataclass
class Pi:
    origin: Path
    checkout: Path
    stubs: Path

    def release(self, tag: str, *, migration: bool = False, branch: str = "main") -> None:
        """Commit on the origin and tag it, as release-please does."""
        _git(self.origin, "checkout", "-q", branch)
        folder = self.origin / ("backend/migrations" if migration else "backend/src")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{tag}.txt").write_text(tag)
        _git(self.origin, "add", ".")
        _git(self.origin, "commit", "-qm", tag)
        _git(self.origin, "tag", tag)
        _git(self.origin, "checkout", "-q", "main")

    def health(self, version: str | None) -> None:
        path = self.stubs / "health"
        if version is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(f'{{"status":"ok","version":"{version}","bot_enabled":true}}')

    def fail(self, step: str) -> None:
        (self.stubs / f"fail-{step}").touch()

    def deploy(self) -> subprocess.CompletedProcess[str]:
        assert BASH is not None
        env = {
            **os.environ,
            "PATH": f"{self.stubs}{os.pathsep}{os.environ['PATH']}",
            "STUB_DIR": str(self.stubs),
            "TC_REPO_DIR": str(self.checkout),
            "TC_DEPLOY_REMOTE": str(self.origin),
            "TC_HEALTH_TIMEOUT": "1",
            "TC_HEALTH_INTERVAL": "0.1",
        }
        return subprocess.run(  # noqa: S603 - our own script, no shell
            [BASH, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
        )

    def docker_calls(self) -> list[str]:
        log = self.stubs / "docker.log"
        return log.read_text().splitlines() if log.exists() else []

    def at(self) -> str:
        return _git(self.checkout, "describe", "--tags", "--always")


@pytest.fixture
def pi(tmp_path: Path) -> Pi:
    origin, checkout, stubs = tmp_path / "origin", tmp_path / "pi", tmp_path / "stubs"
    origin.mkdir()
    stubs.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "commit", "-q", "--allow-empty", "-m", "start")
    for name, body in (("docker", DOCKER), ("curl", CURL)):
        (stubs / name).write_text(body, newline="\n")
        (stubs / name).chmod(0o755)
    made = Pi(origin, checkout, stubs)
    made.release("v0.1.0")
    _git(tmp_path, "clone", "-q", str(origin), str(checkout))
    _git(checkout, "-c", "advice.detachedHead=false", "checkout", "-q", "v0.1.0")
    return made


BACKUP = "compose exec -T app training-coach backup"
ONE_OFF_BACKUP = "compose run --rm --no-deps -T app training-coach backup"
BUILD = "compose up -d --build"


def test_a_new_release_is_backed_up_then_built_and_checked(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    assert pi.at() == "v0.2.0"
    assert pi.docker_calls() == [BACKUP, BUILD]
    assert "deployed v0.2.0" in result.stdout


def test_nothing_new_does_nothing_and_says_nothing(pi: Pi) -> None:
    result = pi.deploy()
    assert (result.returncode, result.stdout, pi.docker_calls()) == (0, "", [])


def test_the_newest_version_wins_not_the_newest_tag(pi: Pi) -> None:
    pi.release("v0.10.0")
    pi.release("v0.9.0")  # tagged later, but older
    pi.health("0.10.0")
    assert pi.deploy().returncode == 0
    assert pi.at() == "v0.10.0"


def test_a_failed_backup_deploys_nothing(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.fail("backup")
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.1.0"
    assert pi.docker_calls() == [BACKUP, ONE_OFF_BACKUP]
    assert "backup failed" in result.stdout


def test_a_stopped_app_is_backed_up_from_a_one_off_container(pi: Pi) -> None:
    # The app being down is when a fix release matters most; exec can't reach it then.
    pi.release("v0.2.0")
    pi.fail("exec")
    pi.health("0.2.0")
    assert pi.deploy().returncode == 0
    assert pi.docker_calls() == [BACKUP, ONE_OFF_BACKUP, BUILD]


def test_a_moved_release_tag_is_refused_and_says_so(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.2.0")
    pi.deploy()
    _git(pi.origin, "commit", "-q", "--allow-empty", "-m", "rewritten")
    _git(pi.origin, "tag", "-f", "v0.2.0")
    pi.release("v0.3.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.2.0"
    assert "a release tag moved" in result.stdout


def test_a_rollback_waits_for_the_old_version_not_any_answer(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.9")  # something answers, but neither the new nor the old version
    result = pi.deploy()
    assert result.returncode == 1
    assert "not healthy either" in result.stdout


def test_an_unhealthy_release_rolls_back_and_is_not_retried(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")  # the new version never answers
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.1.0"
    assert pi.docker_calls() == [BACKUP, BUILD, BUILD]
    assert "rolled back to v0.1.0" in result.stdout

    again = pi.deploy()
    assert (again.returncode, len(pi.docker_calls())) == (0, 3)  # left for a person


def test_a_fixed_release_after_a_failed_one_deploys(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.deploy()
    pi.release("v0.2.1")
    pi.health("0.2.1")
    assert pi.deploy().returncode == 0
    assert pi.at() == "v0.2.1"
    assert not (pi.checkout / ".git" / "auto-deploy-failed").exists()


def test_an_unhealthy_release_with_a_migration_is_left_for_a_person(pi: Pi) -> None:
    pi.release("v0.2.0", migration=True)
    pi.fail("up")
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.2.0"  # rolling back the code alone would break on the new schema
    assert pi.docker_calls() == [BACKUP, BUILD]
    assert "changed the schema" in result.stdout


def test_a_tag_that_is_not_on_main_is_refused(pi: Pi) -> None:
    _git(pi.origin, "checkout", "-q", "-b", "side")
    _git(pi.origin, "checkout", "-q", "main")
    pi.release("v0.2.0", branch="side")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert "not on main" in result.stdout


def test_local_changes_are_never_deployed_over(pi: Pi) -> None:
    (pi.checkout / "backend" / "src" / "v0.1.0.txt").write_text("edited on the Pi")
    pi.release("v0.2.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert "local changes" in result.stdout


def test_a_checkout_ahead_of_the_release_is_left_alone(pi: Pi) -> None:
    pi.release("v0.2.0")
    _git(pi.checkout, "fetch", "-q", "origin", "main")
    _git(pi.checkout, "checkout", "-q", "FETCH_HEAD")
    pi.release("v0.3.0", branch="main")
    _git(pi.checkout, "commit", "-q", "--allow-empty", "-m", "made on the Pi")
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.docker_calls() == []
    assert "not behind v0.3.0" in result.stdout
