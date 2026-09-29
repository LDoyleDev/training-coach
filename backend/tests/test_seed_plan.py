"""Guards the seed plan file until the loader (step 1-B) exists."""

import tomllib
from importlib.resources import files


def _plan() -> dict[str, list[dict[str, object]]]:
    raw = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    return tomllib.loads(raw)


def test_every_session_item_references_a_known_exercise() -> None:
    plan = _plan()
    slugs = {e["slug"] for e in plan["exercises"]}
    for session in plan["sessions"]:
        for item in session["items"]:  # type: ignore[attr-defined]
            assert item["exercise"] in slugs


def test_ladder_start_is_within_ladder() -> None:
    for exercise in _plan()["exercises"]:
        assert 0 <= exercise["start"] < len(exercise["ladder"])  # type: ignore[operator,arg-type]


def test_rep_ranges_are_valid() -> None:
    for session in _plan()["sessions"]:
        for item in session["items"]:  # type: ignore[attr-defined]
            assert 1 <= item["rep_min"] <= item["rep_max"]
