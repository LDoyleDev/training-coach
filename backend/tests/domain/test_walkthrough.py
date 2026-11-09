"""The walk-through (ADR-0092): the tapped days, the placement as stored, the starter by days
and the day it starts."""

from datetime import date

import pytest

from training_coach.domain.walkthrough import (
    Answers,
    CanDo,
    Start,
    landing,
    placement_from_json,
    placement_json,
    placement_problem,
    start_day,
    starter_days,
)

MONDAY = date(2026, 11, 9)
TWO, THREE, FOUR = (2, 3), (1, 1, 2), (0, 1, 0, 2)  # the starters' rest places (plan.toml)


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


LADDERS = {"push-up": [11, 12, 13], "plank": [20, 21]}


@pytest.mark.parametrize(
    ("placement", "why"),
    [
        ({"push-up": ((11, CanDo.YES), (12, CanDo.NO)), "plank": ()}, None),
        ({"deadlift": ((1, CanDo.YES),)}, "isn't one of"),
        ({"plank": ((11, CanDo.YES),)}, "only the steps of its ladder"),
        ({"plank": ((20, CanDo.NO), (21, CanDo.NO), (20, CanDo.NO))}, "each asked once"),
    ],
)
def test_the_placement_answers_only_name_the_walk_throughs_ladders_and_their_steps(
    placement: dict[str, tuple[tuple[int, CanDo], ...]], why: str | None
) -> None:
    found = placement_problem(placement, LADDERS)
    assert found is None if why is None else why in (found or "")


@pytest.mark.parametrize(
    ("tapped", "days"), [(0, 3), (1, 2), (2, 2), (3, 3), (4, 4), (5, 4), (7, 4)]
)
def test_the_starter_is_picked_by_the_days_tapped(tapped: int, days: int) -> None:
    assert starter_days(tapped) == days


def test_each_session_lands_after_the_rest_places_before_it() -> None:
    assert landing(MONDAY, THREE) == (MONDAY, date(2026, 11, 11), date(2026, 11, 13))


def test_monday_wednesday_friday_starts_today_on_the_3_day_and_misses_nothing() -> None:
    assert start_day(MONDAY, (0, 2, 4), THREE) == Start(MONDAY, ())


def test_the_start_is_the_tapped_day_that_lands_the_most_sessions_not_the_first() -> None:
    """Tue, Thu, Sat tapped on a Monday: from Tuesday A Tue, B Thu, C Sat."""
    assert start_day(MONDAY, (5, 1, 3), THREE) == Start(date(2026, 11, 10), ())


def test_days_that_dont_fit_the_pattern_are_named() -> None:
    """Mon and Tue on the 2-day (A, two rest places, B): one of them is always missed, so the
    first, today, wins, and Tuesday is named."""
    assert start_day(MONDAY, (0, 1), TWO) == Start(MONDAY, (1,))


def test_a_tapped_day_later_in_the_week_starts_then() -> None:
    found = start_day(MONDAY, (3, 4, 5, 6), FOUR)
    assert found.on == date(2026, 11, 12)  # Thu: L1 Thu, U1 Fri, L2 Sun, U2 Mon
    assert found.missed == (5,)


def test_nothing_tapped_starts_tomorrow() -> None:
    assert start_day(MONDAY, (), THREE) == Start(date(2026, 11, 10), ())
