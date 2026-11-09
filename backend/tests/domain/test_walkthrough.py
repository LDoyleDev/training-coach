"""The walk-through's answers (ADR-0092): the tapped days, and the placement as stored."""

import pytest

from training_coach.domain.walkthrough import (
    Answers,
    CanDo,
    placement_from_json,
    placement_json,
)


def test_nothing_answered_is_a_valid_set_of_answers() -> None:
    answers = Answers()
    assert answers.age_band is None
    assert answers.weekdays == ()
    assert answers.placement == {}


@pytest.mark.parametrize(("days", "why"), [((7,), r"0 \(Monday\)"), ((0, 0), "twice")])
def test_a_weekday_is_monday_to_sunday_and_tapped_once(days: tuple[int, ...], why: str) -> None:
    with pytest.raises(ValueError, match=why):
        Answers(weekdays=days)


def test_the_placement_goes_into_json_and_back_unchanged() -> None:
    placement = {
        "push-up": ((11, CanDo.YES), (12, CanDo.NOT_SURE)),
        "split-squat": ((30, CanDo.SKIP),),
    }
    stored = placement_json(placement)
    assert stored == {"push-up": [[11, "yes"], [12, "not_sure"]], "split-squat": [[30, "skip"]]}
    assert placement_from_json(stored) == placement
