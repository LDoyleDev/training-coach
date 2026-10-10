"""scripts/offsite-backup.sh (ADR-0042), run for real with stub ``age`` and ``rclone``.

``age`` writes "ENCRYPTED(<recipient>):" plus the input to its output; ``rclone`` keeps the
"bucket" as a folder and supports the lsf, copyto and delete calls the script makes.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "offsite-backup.sh"
BASH = os.environ.get("TC_TEST_BASH") or (shutil.which("bash") if sys.platform != "win32" else None)

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32",
    reason="needs bash and POSIX file modes (the settings file must be 600); runs in CI",
)

RECIPIENT = "age1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
AGE = """#!/usr/bin/env bash
# age -r RECIPIENT -o OUT IN
out="$4"; { printf 'ENCRYPTED(%s):' "$2"; cat "$5"; } > "$out"
"""
RCLONE = """#!/usr/bin/env bash
echo "$*" >> "$STUB_DIR/rclone.log"
bucket="$STUB_DIR/bucket"; mkdir -p "$bucket"
case "$1" in
  lsf) ls "$bucket" ;;
  copyto) cp "$3" "$bucket/$(basename "$4")" ;;
  delete) find "$bucket" -name 'training_coach-*.db.age' -mtime +"${3%d}" -delete ;;
esac
"""


@pytest.fixture
def pi(tmp_path: Path) -> Path:
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in (("age", AGE), ("rclone", RCLONE)):
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)
    (tmp_path / "backups").mkdir()
    env = tmp_path / "offsite.env"
    env.write_text(f"TC_BACKUP_AGE_RECIPIENT={RECIPIENT}\nTC_OFFSITE_BUCKET=coach-backups\n")
    env.chmod(0o600)
    return tmp_path


def _run(pi: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    env = {
        **os.environ,
        "PATH": f"{pi / 'stubs'}{os.pathsep}{os.environ['PATH']}",
        "STUB_DIR": str(pi),
        "TC_OFFSITE_ENV": str(pi / "offsite.env"),
        "TC_BACKUPS_DIR": str(pi / "backups"),
    }
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [BASH, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def _backup(pi: Path, day: str, age_days: float = 0) -> Path:
    path = pi / "backups" / f"training_coach-{day}.db"
    path.write_bytes(b"SQLite format 3\x00 personal data")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


def test_the_newest_backup_goes_off_site_encrypted_once(pi: Path) -> None:
    _backup(pi, "2026-10-09", age_days=1)
    _backup(pi, "2026-10-10")
    done = _run(pi)
    assert done.returncode == 0, done.stderr
    (stored,) = (pi / "bucket").iterdir()
    assert stored.name == "training_coach-2026-10-10.db.age"
    assert stored.read_bytes().startswith(f"ENCRYPTED({RECIPIENT}):".encode())
    again = _run(pi)
    assert again.returncode == 0
    assert "already off-site" in again.stdout
    assert len(list((pi / "bucket").iterdir())) == 1


def test_copies_older_than_the_retention_are_deleted(pi: Path) -> None:
    _backup(pi, "2026-10-10")
    (pi / "bucket").mkdir()
    old = pi / "bucket" / "training_coach-2026-08-01.db.age"
    old.write_text("old")
    stamp = time.time() - 40 * 86400
    os.utime(old, (stamp, stamp))
    assert _run(pi).returncode == 0
    assert not old.exists()
    assert "--min-age 35d" in (pi / "rclone.log").read_text()


def test_stale_backups_fail_loudly(pi: Path) -> None:
    _backup(pi, "2026-10-01", age_days=9)
    done = _run(pi)
    assert done.returncode == 1
    assert "no nightly backup newer than 2 days" in done.stderr


def test_a_readable_settings_file_is_refused(pi: Path) -> None:
    _backup(pi, "2026-10-10")
    (pi / "offsite.env").chmod(0o644)
    done = _run(pi)
    assert done.returncode == 1
    assert "must be mode 600" in done.stderr


def test_a_recipient_that_isnt_an_age_key_is_refused(pi: Path) -> None:
    _backup(pi, "2026-10-10")
    (pi / "offsite.env").write_text("TC_BACKUP_AGE_RECIPIENT=hunter2\nTC_OFFSITE_BUCKET=b\n")
    (pi / "offsite.env").chmod(0o600)
    done = _run(pi)
    assert done.returncode == 1
    assert "isn't an age public key" in done.stderr


def test_the_script_is_executable_in_git() -> None:
    """The timer runs it directly (review of #162): mode 100755 in the repository."""
    listed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["git", "ls-files", "-s", str(SCRIPT)],  # noqa: S607
        cwd=SCRIPT.parent,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert listed.startswith("100755"), listed
