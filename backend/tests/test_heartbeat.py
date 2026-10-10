"""scripts/heartbeat.sh (ADR-0045), run for real with a stub ``curl``.

``curl`` answers the health URL with whatever the test wrote to a file, and records every other
call (the pings) with its arguments.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "heartbeat.sh"
BASH = os.environ.get("TC_TEST_BASH") or (shutil.which("bash") if sys.platform != "win32" else None)

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32",
    reason="needs bash and POSIX file modes (the settings file must be 600); runs in CI",
)

HEALTH = "http://127.0.0.1:8095/healthz"
PING = "https://hc-ping.com/0b3c1c8e-test"
CURL = f"""#!/usr/bin/env bash
for arg in "$@"; do last="$arg"; done
if [ "$last" = "{HEALTH}" ]; then
  cat "$STUB_DIR/health" 2>/dev/null || exit 7
  exit 0
fi
echo "$*" >> "$STUB_DIR/pings.log"
[ ! -e "$STUB_DIR/offline" ] || exit 6
"""


@pytest.fixture
def pi(tmp_path: Path) -> Path:
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "curl").write_text(CURL)
    (stubs / "curl").chmod(0o755)
    settings = tmp_path / "heartbeat.env"
    settings.write_text(f"TC_HEARTBEAT_URL={PING}\n")
    settings.chmod(0o600)
    return tmp_path


def _run(pi: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    env = {
        **os.environ,
        "PATH": f"{pi / 'stubs'}{os.pathsep}{os.environ['PATH']}",
        "STUB_DIR": str(pi),
        "TC_HEARTBEAT_ENV": str(pi / "heartbeat.env"),
    }
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [BASH, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def _pings(pi: Path) -> list[str]:
    log = pi / "pings.log"
    return log.read_text().splitlines() if log.exists() else []


def test_a_healthy_app_pings(pi: Path) -> None:
    (pi / "health").write_text('{"status":"ok","version":"0.21.0"}')
    result = _run(pi)
    assert result.returncode == 0, result.stderr
    (ping,) = _pings(pi)
    assert ping.endswith(PING)
    assert "/fail" not in ping


@pytest.mark.parametrize("answer", [None, '{"status":"starting"}'])
def test_an_app_that_does_not_answer_reports_a_failure(pi: Path, answer: str | None) -> None:
    """The Pi is up but the app isn't: say so at once, not after the grace period."""
    if answer is not None:
        (pi / "health").write_text(answer)
    result = _run(pi)
    assert result.returncode == 0, result.stderr
    (ping,) = _pings(pi)
    assert ping.endswith(f"{PING}/fail")
    assert "healthz:" in ping


def test_a_ping_that_cannot_go_out_fails(pi: Path) -> None:
    (pi / "health").write_text('{"status":"ok"}')
    (pi / "offline").touch()
    result = _run(pi)
    assert result.returncode == 1
    assert "the ping didn't go out" in result.stderr


def test_the_settings_must_be_private(pi: Path) -> None:
    (pi / "heartbeat.env").chmod(0o644)
    result = _run(pi)
    assert result.returncode == 1
    assert "must be mode 600" in result.stderr
    assert _pings(pi) == []


@pytest.mark.parametrize("url", ["http://hc-ping.com/x", ""])
def test_the_ping_url_must_be_https(pi: Path, url: str) -> None:
    (pi / "heartbeat.env").write_text(f"TC_HEARTBEAT_URL={url}\n")
    (pi / "health").write_text('{"status":"ok"}')
    result = _run(pi)
    assert result.returncode == 1
    assert _pings(pi) == []


def test_without_settings_nothing_is_sent(pi: Path) -> None:
    (pi / "heartbeat.env").unlink()
    result = _run(pi)
    assert result.returncode == 1
    assert "no settings" in result.stderr
