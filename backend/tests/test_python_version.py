"""The tests run on the Python the Pi runs: the Dockerfile's image. CI once picked 3.14 (26 Oct)."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _image_version() -> tuple[str, str]:
    found = re.findall(r"python:(\d+)\.(\d+)-slim", (ROOT / "Dockerfile").read_text("utf-8"))
    images = {(str(major), str(minor)) for major, minor in found}
    assert len(images) == 1, images
    return images.pop()


def test_python_version_file_names_the_dockerfiles_python() -> None:
    pinned = (ROOT / "backend" / ".python-version").read_text("utf-8").strip()
    assert pinned == ".".join(_image_version())


def test_the_tests_run_on_the_dockerfiles_python() -> None:
    major, minor = _image_version()
    assert sys.version_info[:2] == (int(major), int(minor))
