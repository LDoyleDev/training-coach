"""The lock rule against the cases the web's copy is tested on too (ADR-0092, Decided 19): the
walk-through applies ``domain.locks`` in the browser, so both read one file of cases."""

import json
from pathlib import Path
from typing import Any

import pytest

from training_coach.domain import locks
from training_coach.domain.kit import Item, Resistance
from training_coach.domain.muscles import Kit
from training_coach.domain.step_levels import Mark

CASES = Path(__file__).resolve().parents[3] / "frontend/src/walkthrough/lock-cases.json"


def _cases() -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    return found


def _item(found: dict[str, Any]) -> Item:
    strength = found.get("resistance")
    return Item(
        Kit(found["kit"]),
        found.get("kg"),
        found.get("min_kg"),
        Resistance(strength) if strength is not None else None,
    )


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["case"])
def test_the_rule_gives_each_shared_case_its_answer(case: dict[str, Any]) -> None:
    kit = None if case["kit"] is None else [_item(i) for i in case["kit"]]
    limits = locks.Limits(kit, frozenset(Mark(m) for m in case["avoid"]))
    found = locks.lock(locks.Asks(case["needs"], [Mark(m) for m in case["marks"]]), limits)
    assert found.open is case["open"]
    assert list(found.missing) == case["missing"]
    assert list(found.avoided) == [locks.AVOIDED[Mark(m)] for m in case["avoided"]]


def test_the_cases_cover_open_and_locked_by_kit_and_by_a_mark() -> None:
    cases = _cases()
    assert any(c["open"] for c in cases)
    assert any(c["missing"] for c in cases)
    assert any(c["avoided"] for c in cases)
