"""A cycle draft against the cases the web's copy is tested on too (ADR-0093): the browser
works out the "Saving will" list from the same rules Save checks, so ``domain.cycle`` and
``plan/cycleLogic.ts`` read one file of cases."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from training_coach.domain.cycle import (
    Key,
    Slot,
    add,
    applied,
    cannot_add,
    days,
    move,
    problem,
    remove,
    split,
    suggested_after,
    with_rest,
)
from training_coach.domain.queue import Position, rest_days_left

CASES = Path(__file__).resolve().parents[3] / "frontend/src/plan/cycle-cases.json"
OWNER = tuple(Slot(k) for k in (10, 20, 30, 40, 50, 60, 70))


def _cases(kind: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = json.loads(CASES.read_text(encoding="utf-8"))[kind]
    return found


def _cycle(pairs: list[list[Any]]) -> tuple[Slot, ...]:
    return tuple(Slot(key, rest) for key, rest in pairs)


@pytest.mark.parametrize("case", _cases("split"), ids=lambda c: f"{c['rest_after']} rest days")
def test_a_new_session_splits_the_rest_days_more_before_it(case: dict[str, Any]) -> None:
    assert split(case["rest_after"]) == (case["before"], case["new"])


@pytest.mark.parametrize("case", _cases("add"), ids=lambda c: c["case"])
def test_a_new_session_goes_after_the_longest_gap(case: dict[str, Any]) -> None:
    cycle = _cycle(case["cycle"])
    assert suggested_after(cycle) == case["suggested"]
    found = add(cycle, "n1", case["after"])
    assert found == _cycle(case["result"])
    assert days(found) == case["days"]


@pytest.mark.parametrize("case", _cases("remove"), ids=lambda c: c["case"])
def test_a_removed_sessions_days_go_to_the_one_before(case: dict[str, Any]) -> None:
    found = remove(_cycle(case["cycle"]), case["key"])
    assert found == _cycle(case["result"])
    assert days(found) == case["days"]


@pytest.mark.parametrize("case", _cases("move"), ids=lambda c: c["case"])
def test_up_and_down_move_a_session_with_its_rest_days(case: dict[str, Any]) -> None:
    assert move(_cycle(case["cycle"]), case["key"], case["by"]) == _cycle(case["result"])


@pytest.mark.parametrize("case", _cases("problem"), ids=lambda c: c["case"])
def test_the_limits_say_why_in_words(case: dict[str, Any]) -> None:
    assert problem(_cycle(case["cycle"])) == case["problem"]


@pytest.mark.parametrize("case", _cases("cannot_add"), ids=lambda c: c["case"])
def test_add_is_greyed_with_the_reason(case: dict[str, Any]) -> None:
    assert cannot_add(_cycle(case["cycle"])) == case["reason"]


@pytest.mark.parametrize("case", _cases("applied"), ids=lambda c: c["case"])
def test_the_queue_after_a_draft(case: dict[str, Any]) -> None:
    found = applied(
        _cycle(case["before"]),
        _cycle(case["draft"]),
        Position(case["pointer"], tuple(case["queued"])),
        case["last_done"],
    )
    then = case["then"]
    assert found.cycle == _cycle(case["draft"])
    assert found.pointer == then["pointer"]
    assert found.queued == tuple(then["queued"])
    assert found.added == tuple(then["added"])
    assert found.removed == tuple(then["removed"])
    assert found.moved == tuple(then["moved"])
    assert found.last_rest == then["last_rest"]
    assert found.days == then["days"]
    assert found.changed is then["changed"]


@pytest.mark.parametrize("case", _cases("rest_days_left"), ids=lambda c: c["case"])
def test_the_rest_places_left_as_the_list_reads_them(case: dict[str, Any]) -> None:
    """The queue's rule the "Saving will" list copies to say what today becomes (ADR-0091)."""
    done = date(2026, 11, 10)
    found = rest_days_left(case["rest_after"], done, done + timedelta(days=case["gone"]))
    assert found == case["left"]


def test_positions_follow_the_new_order() -> None:
    found = applied(OWNER, add(OWNER, "n1", 30), Position(40), 30)
    assert found.positions == {10: 0, 20: 1, 30: 2, "n1": 3, 40: 4, 50: 5, 60: 6, 70: 7}


def test_a_rest_day_set_on_one_session() -> None:
    assert with_rest(OWNER, 30, 2)[2] == Slot(30, 2)
    assert days(with_rest(OWNER, 30, 2)) == 9


def test_a_pointer_outside_the_plan_starts_the_new_cycle() -> None:
    assert applied(OWNER, OWNER[1:], Position(99), None).pointer == 20


def test_a_draft_over_a_limit_is_not_applied() -> None:
    with pytest.raises(ValueError, match="at least one session"):
        applied(OWNER, (), Position(10), None)


def test_a_draft_naming_a_session_not_in_the_plan_is_not_applied() -> None:
    with pytest.raises(ValueError, match="session 99 is not in the plan"):
        applied(OWNER, (*OWNER, Slot(99)), Position(10), None)


@pytest.mark.parametrize("key", [99, "n9"])
def test_an_unknown_session_cant_be_edited(key: Key) -> None:
    with pytest.raises(ValueError, match="is not in the cycle"):
        remove(OWNER, key)


def test_an_empty_cycle_has_no_suggestion() -> None:
    with pytest.raises(ValueError, match="no sessions"):
        suggested_after(())
