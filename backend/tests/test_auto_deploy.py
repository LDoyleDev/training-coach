"""scripts/auto-deploy.sh (ADR-0030), run for real against throwaway git repos.

``docker`` and ``curl`` are stubs on PATH: docker records its calls (and can be told to fail
the backup or the rebuild, or which images it has), curl answers /healthz with whatever the
test wrote to a file.
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
  image\\ inspect*) cat "$STUB_DIR/running" 2>/dev/null ;;
  image\\ ls*) cat "$STUB_DIR/images" 2>/dev/null || true ;;
  compose\\ ps*) [ ! -e "$STUB_DIR/replaced" ] || echo c0ffee ;;
  inspect\\ *c0ffee) cat "$STUB_DIR/replaced" ;;
  *exec*backup*) [ ! -e "$STUB_DIR/fail-backup" ] && [ ! -e "$STUB_DIR/fail-exec" ] ;;
  *backup*) [ ! -e "$STUB_DIR/fail-backup" ] ;;
  *up\\ -d*) [ ! -e "$STUB_DIR/fail-up" ] ;;
esac
"""
CURL = """#!/usr/bin/env bash
cat "$STUB_DIR/health" 2>/dev/null || exit 7
"""
# Signs with the fingerprint in sign-as (beside it) written into the signature, and verifies by
# reading it back, answering with gpg's status lines; "bad" makes a signature that won't verify.
GPG = """#!/usr/bin/env bash
mode="" file=""
while [ $# -gt 0 ]; do
  case "$1" in
    --import) cp "$2" "$STUB_DIR/imported"; exit 0 ;;  # the key the script trusts, kept to look at
    --verify) mode=verify; file="$2"; shift ;;
    -bsau) mode=sign ;;
  esac
  shift
done
cat >/dev/null
if [ "$mode" = sign ]; then
  echo "[GNUPG:] SIG_CREATED D" >&2
  printf -- '-----BEGIN PGP SIGNATURE-----\\n\\n%s\\n-----END PGP SIGNATURE-----\\n' \\
    "$(cat "$(dirname "$0")/sign-as")"  # beside the stub: commits run without STUB_DIR
  exit 0
fi
signer=$(sed -n 3p "$file")
echo "[GNUPG:] NEWSIG"  # as gpg does: git looks for the lines after it
if [ "$signer" = bad ]; then
  echo "[GNUPG:] BADSIG 0 GitHub"
  exit 1
fi
echo "[GNUPG:] GOODSIG 0 GitHub"
echo "[GNUPG:] VALIDSIG $signer 2026-10-10 0 0 4 0 1 8 00 $signer"
"""
GITHUB = "968479A1AFF927E37D1A566BB5690EEEBB952194"  # pinned in the script
KEY = "scripts/keys/github-web-flow.gpg"  # the script imports it from the deployed commit


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

    def release(
        self,
        tag: str,
        *,
        migration: bool = False,
        branch: str = "main",
        signer: str | None = GITHUB,
    ) -> None:
        """Commit on the origin and tag it, as release-please does; signed by GitHub, as a merge
        on github.com is, unless ``signer`` says otherwise (None: not signed)."""
        _git(self.origin, "checkout", "-q", branch)
        folder = self.origin / ("backend/migrations" if migration else "backend/src")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{tag}.txt").write_text(tag)
        _git(self.origin, "add", ".")
        if signer is None:
            _git(self.origin, "commit", "-qm", tag)
        else:
            (self.stubs / "sign-as").write_text(signer)
            gpg = f"gpg.program={(self.stubs / 'gpg').as_posix()}"
            _git(self.origin, "-c", gpg, "-c", "user.signingkey=x", "commit", "-q", "-S", "-m", tag)
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

    def deploy(self, **extra: str) -> subprocess.CompletedProcess[str]:
        return self._bash([str(SCRIPT)], **extra)

    def unsigned_commit(self, since: str, release: str) -> str:
        """The script's own check, called directly: sourced, the script only defines it."""
        command = 'source "$1" && cd "$2" && unsigned_commit "$3" "$4"'
        args = [SCRIPT.as_posix(), self.checkout.as_posix(), since, release]
        result = self._bash(["-c", command, "test", *args])
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def _bash(self, argv: list[str], **extra: str) -> subprocess.CompletedProcess[str]:
        assert BASH is not None
        env = {
            **os.environ,
            "PATH": f"{self.stubs}{os.pathsep}{os.environ['PATH']}",
            "STUB_DIR": str(self.stubs),
            "TC_REPO_DIR": str(self.checkout),
            "TC_DEPLOY_REMOTE": str(self.origin),
            "TC_HEALTH_TIMEOUT": "1",
            "TC_HEALTH_INTERVAL": "0.1",
            **extra,
        }
        return subprocess.run(  # noqa: S603 - our own script, no shell
            [BASH, *argv], env=env, capture_output=True, text=True, check=False
        )

    def docker_calls(self) -> list[str]:
        """The compose calls that act: the deploy's steps, without the image bookkeeping."""
        log = self.stubs / "docker.log"
        calls = log.read_text().splitlines() if log.exists() else []
        return [c for c in calls if c.startswith("compose ") and not c.startswith("compose ps")]

    def removed_images(self) -> list[str]:
        log = self.stubs / "docker.log"
        calls = log.read_text().splitlines() if log.exists() else []
        return [call.removeprefix("image rm ") for call in calls if call.startswith("image rm ")]

    def images(self, running: str, *others: str, replaced: str | None = None) -> None:
        """This app's images, newest first, as `docker image ls` lists them; ``running`` once
        the deploy is done, ``replaced`` the one the app's container ran before it."""
        (self.stubs / "running").write_text(running + "\n")
        (self.stubs / "images").write_text("".join(f"{i}\n" for i in (running, *others)))
        if replaced is not None:
            (self.stubs / "replaced").write_text(replaced + "\n")

    def cut_off_builds(self, *numbers: int) -> None:
        """The script is killed during these rebuilds (1 is the first): a power cut, a reboot,
        the unit's TimeoutStartSec."""
        cut = " ".join(map(str, numbers))
        stub = DOCKER.replace(
            "#!/usr/bin/env bash\n",
            '#!/usr/bin/env bash\ncase "$*" in *up\\ -d*) echo >> "$STUB_DIR/builds"\n'
            f'  case " {cut} " in *" $(($(wc -l < "$STUB_DIR/builds"))) "*)\n'
            '    echo "$*" >> "$STUB_DIR/docker.log"; kill -9 $PPID; exit 1 ;; esac ;; esac\n',
            1,
        )
        (self.stubs / "docker").write_text(stub, newline="\n")

    def at(self) -> str:
        return _git(self.checkout, "describe", "--tags", "--always")


@pytest.fixture
def pi(tmp_path: Path) -> Pi:
    origin, checkout, stubs = tmp_path / "origin", tmp_path / "pi", tmp_path / "stubs"
    origin.mkdir()
    stubs.mkdir()
    _git(origin, "init", "-q", "-b", "main")
    (origin / KEY).parent.mkdir(parents=True)
    (origin / KEY).write_text("GitHub's key")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "start")
    for name, body in (("docker", DOCKER), ("curl", CURL), ("gpg", GPG)):
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


def test_a_release_tag_deleted_and_made_again_elsewhere_is_refused(pi: Pi) -> None:
    """The fetch refuses a tag moved in place, but --prune drops one deleted upstream first, so
    made again on a later commit it arrived as new (security test of 2026-10-24)."""
    pi.release("v0.2.0")
    pi.health("0.2.0")
    assert pi.deploy().returncode == 0
    deployed = _git(pi.checkout, "rev-parse", "HEAD")
    _git(pi.origin, "tag", "-d", "v0.2.0")
    pi.deploy()  # drops the local tag
    (pi.origin / "backend" / "src" / "later.txt").write_text("not released")
    pi.release("v0.2.0")  # signed, on main and forward: only this Pi's history tells
    result = pi.deploy()
    assert result.returncode == 1
    assert _git(pi.checkout, "rev-parse", "HEAD") == deployed
    assert pi.docker_calls() == [BACKUP, BUILD]
    assert f"v0.2.0 was deployed here at {deployed[:7]}" in result.stdout


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


@pytest.mark.parametrize(
    "signer",
    [None, "0123456789ABCDEF0123456789ABCDEF01234567", "bad"],
    ids=["unsigned", "someone-else", "bad-signature"],
)
def test_a_release_github_did_not_sign_is_refused(pi: Pi, signer: str | None) -> None:
    """On main is not enough: a commit pushed there past the pull requests (a stolen token, an
    admin override) isn't signed by GitHub's key, so it doesn't deploy."""
    pi.release("v0.2.0", signer=signer)
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert "which GitHub didn't sign" in result.stdout


def test_an_unsigned_commit_under_a_signed_release_is_refused(pi: Pi) -> None:
    """A commit pushed past the pull requests, then a signed release on top of it (the next
    merge): every commit since the deployed version is checked, not only the release's."""
    _git(pi.origin, "commit", "-q", "--allow-empty", "-m", "pushed past the pull requests")
    pushed = _git(pi.origin, "rev-parse", "--short", "HEAD")
    pi.release("v0.2.0")
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert f"v0.2.0 includes {pushed}, which GitHub didn't sign" in result.stdout


def test_the_signature_check_fails_closed(pi: Pi) -> None:
    """Commits it can't list (an unknown ref, a broken repo) or no commits at all count as
    unsigned, not as checked; main's own checks shouldn't be what saves it."""
    pi.release("v0.2.0")
    _git(pi.checkout, "fetch", "-q", "--tags")
    assert pi.unsigned_commit("v0.1.0", "v0.2.0") == ""  # the signed release passes
    assert pi.unsigned_commit("v0.1.0", "no-such-ref") == "no-such-ref"
    assert pi.unsigned_commit("v0.2.0", "v0.2.0") == "v0.2.0"  # nothing to check


def test_without_gpg_nothing_deploys(pi: Pi) -> None:
    """No check means no deploy, not a deploy without the check."""
    pi.release("v0.2.0")
    pi.health("0.2.0")
    result = pi.deploy(TC_DEPLOY_GPG="no-such-gpg")
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert "gpg is needed" in result.stdout


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


PENDING = Path(".git") / "auto-deploy-pending"
FAILED = Path(".git") / "auto-deploy-failed"


def test_a_deploy_cut_off_mid_build_is_finished_next_time(pi: Pi) -> None:
    """Killed after the checkout moved: HEAD is already on the tag, but the old image runs."""
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.cut_off_builds(1)
    assert pi.deploy().returncode != 0
    assert pi.at() == "v0.2.0"

    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    assert pi.docker_calls() == [BACKUP, BUILD, BUILD]  # no second backup: one was taken
    assert "finishing the deploy of v0.2.0" in result.stdout
    assert not (pi.checkout / PENDING).exists()


def test_a_deploy_cut_off_twice_is_rolled_back(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.cut_off_builds(1, 2)
    pi.deploy()
    pi.deploy()
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.1.0"
    assert pi.docker_calls() == [BACKUP, BUILD, BUILD, BUILD]  # the third is the rollback's
    assert "rolled back to v0.1.0" in result.stdout
    assert (pi.checkout / FAILED).read_text().strip() == "v0.2.0"


def test_a_rollback_cut_off_is_finished_once_then_left(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.cut_off_builds(2)  # the rollback's build
    pi.deploy()
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.1.0"
    assert "rolled back to v0.1.0" in result.stdout

    again = pi.deploy()
    assert (again.returncode, len(pi.docker_calls())) == (0, 4)  # not retried after that


def test_a_cut_off_deploy_overtaken_by_hand_is_left_for_a_person(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.cut_off_builds(1)
    pi.deploy()
    pi.release("v0.3.0")
    _git(pi.checkout, "fetch", "-q", "--tags")
    _git(pi.checkout, "checkout", "-q", "v0.3.0")  # deployed by hand meanwhile
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), len(pi.docker_calls())) == ("v0.3.0", 2)
    assert "doesn't match the checkout" in result.stdout


@pytest.mark.parametrize(
    ("branch", "refused"), [("side", "not on main"), ("main", "which GitHub didn't sign")]
)
def test_a_planted_pending_mark_does_not_skip_the_checks(pi: Pi, branch: str, refused: str) -> None:
    """The mark is a file in .git: one naming an unsigned tag was "finished" and deployed, off
    main too. A resumed deploy passes the same checks as a new one (security test of
    2026-10-24)."""
    _git(pi.origin, "branch", "side")
    pi.release("v0.9.0", branch=branch, signer=None)
    _git(pi.checkout, "fetch", "-q", "origin", "refs/tags/v0.9.0:refs/tags/v0.9.0")
    _git(pi.checkout, "fetch", "-q", "origin", "+main:refs/remotes/deploy/main")  # a run's fetch
    head = _git(pi.checkout, "rev-parse", "HEAD")
    (pi.checkout / PENDING).write_text(f"v0.9.0 {head}\n", newline="\n")  # as the script writes
    pi.health("0.9.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert refused in result.stdout


@pytest.mark.parametrize("mark", ["--orphan=x {head}", "main {head}", "v0.2.0 HEAD"])
def test_a_pending_mark_this_script_did_not_write_is_refused(pi: Pi, mark: str) -> None:
    """Only a release tag and a full commit id: nothing in the mark reaches git as an option
    or as a branch or other name."""
    pi.release("v0.2.0")
    _git(pi.checkout, "fetch", "-q", "--tags")
    head = _git(pi.checkout, "rev-parse", "HEAD")
    (pi.checkout / PENDING).write_text(mark.format(head=head) + "\n", newline="\n")
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 1
    assert (pi.at(), pi.docker_calls()) == ("v0.1.0", [])
    assert "is not one this script wrote" in result.stdout


def test_a_resumed_deploy_trusts_the_key_deployed_before(pi: Pi) -> None:
    """When a cut-off deploy is finished the release is checked out already, so its own copy of
    GitHub's key could vouch for it; the key comes from the commit deployed before."""
    (pi.origin / KEY).write_text("a key the release brought")
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.cut_off_builds(1)
    pi.deploy()
    (pi.stubs / "imported").unlink()
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (pi.stubs / "imported").read_text() == "GitHub's key"


def test_the_rollback_runs_even_if_the_failed_mark_cannot_be_written(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    (pi.checkout / FAILED).mkdir()  # stands in for a full disk: the write fails as ENOSPC would
    result = pi.deploy()
    assert result.returncode == 1
    assert pi.at() == "v0.1.0"
    assert pi.docker_calls() == [BACKUP, BUILD, BUILD], result.stdout + result.stderr
    assert "rolled back to v0.1.0" in result.stdout


def test_a_tag_deleted_upstream_is_dropped_and_blocks_nothing(pi: Pi) -> None:
    pi.release("v9.9.9")  # a typo'd tag; the app's version.txt never says 9.9.9
    pi.health("0.1.0")
    assert pi.deploy().returncode == 1  # rolled back, marked failed
    _git(pi.origin, "tag", "-d", "v9.9.9")
    pi.release("v0.2.0")
    pi.health("0.2.0")
    result = pi.deploy()
    assert result.returncode == 0, result.stdout + result.stderr
    assert pi.at() == "v0.2.0"
    assert _git(pi.checkout, "tag", "--list", "v9.9.9") == ""


def test_a_healthy_deploy_removes_old_images_but_the_running_and_previous(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.2.0")
    pi.images(
        "sha256:new", "sha256:previous", "sha256:old", "sha256:older", replaced="sha256:previous"
    )
    assert pi.deploy().returncode == 0
    assert pi.removed_images() == ["sha256:old", "sha256:older"]
    assert "image ls --quiet --no-trunc --filter label=training-coach.app" in (
        (pi.stubs / "docker.log").read_text()
    )  # only this app's images


def test_a_failed_deploy_removes_no_images(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.1.0")
    pi.images("sha256:new", "sha256:previous", "sha256:old", replaced="sha256:previous")
    assert pi.deploy().returncode == 1
    assert pi.removed_images() == []


def test_the_clean_up_keeps_the_image_that_ran_before_not_the_newest_other(pi: Pi) -> None:
    """After a rollback by hand whose build was all cached, the image that ran is older than one
    that never ran, and keeping the newest other removed it (security test of 2026-10-24)."""
    pi.release("v0.2.0")
    pi.health("0.2.0")
    pi.images("sha256:new", "sha256:never-ran", "sha256:ran", replaced="sha256:ran")
    assert pi.deploy().returncode == 0
    assert pi.removed_images() == ["sha256:never-ran"]


def test_the_clean_up_removes_nothing_when_what_ran_before_is_unknown(pi: Pi) -> None:
    pi.release("v0.2.0")
    pi.health("0.2.0")
    pi.images("sha256:new", "sha256:previous", "sha256:old")  # the app wasn't running
    result = pi.deploy()
    assert result.returncode == 0
    assert pi.removed_images() == []
    assert "which one ran before this deploy isn't known" in result.stdout
