"""The starter and the start day against the cases the web's copy is tested on too (ADR-0092,
How the plan is made 3 and 8): the browser picks both from the tapped days, which never reach
the server without consent, so ``domain.walkthrough`` and ``days.ts`` read one file of cases."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from training_coach.domain.walkthrough import Start, landing, start_day, starter_days

CASES = Path(__file__).resolve().parents[3] / "frontend/src/walkthrough/day-cases.json"


def _cases(kind: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = json.loads(CASES.read_text(encoding="utf-8"))[kind]
    return found


@pytest.mark.parametrize("case", _cases("starter_days"), ids=lambda c: f"{c['tapped']} tapped")
def test_the_starter_is_picked_by_the_days_tapped(case: dict[str, Any]) -> None:
    assert starter_days(case["tapped"]) == case["days"]


@pytest.mark.parametrize("case", _cases("landing"), ids=lambda c: c["case"])
def test_each_session_lands_after_the_rest_places_before_it(case: dict[str, Any]) -> None:
    found = landing(date.fromisoformat(case["start"]), case["rest_after"])
    assert found == tuple(date.fromisoformat(d) for d in case["days"])


@pytest.mark.parametrize("case", _cases("start_day"), ids=lambda c: c["case"])
def test_the_start_day_of_each_shared_case(case: dict[str, Any]) -> None:
    found = start_day(date.fromisoformat(case["today"]), case["weekdays"], case["rest_after"])
    assert found == Start(date.fromisoformat(case["on"]), tuple(case["missed"]))
