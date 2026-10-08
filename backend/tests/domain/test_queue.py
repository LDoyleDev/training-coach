from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import (
    Position,
    caught_up,
    complete,
    local_date,
    next_in_cycle,
    swap_with_next,
    upcoming,
)

ORDER = [10, 20, 30, 40, 50, 60, 70]  # legs, zone2, upper, cardio, legs-core, intervals, arms
BERLIN = ZoneInfo("Europe/Berlin")
DONE, REST, SKIPPED = WorkoutStatus.DONE, WorkoutStatus.REST, WorkoutStatus.SKIPPED


def replay(days: list[list[tuple[int | None, WorkoutStatus]]], pointer: int = 10) -> list[int]:
    """Pointer at the start of each day, then the final pointer."""
    seen = []
    position = Position(pointer)
    for workouts in days:
        seen.append(position.pointer)
        for template_id, status in workouts:
            position = complete(ORDER, position, template_id, status)
    return [*seen, position.pointer]


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        pytest.param([[(10, DONE)], [(20, DONE)]], [10, 20, 30], id="normal-days"),
        pytest.param([[], [(10, DONE)]], [10, 10, 20], id="missed-day-shifts-back"),
        pytest.param([[], [], [(10, DONE)]], [10, 10, 10, 20], id="double-skip"),
        pytest.param([[(10, SKIPPED)], [(10, DONE)]], [10, 10, 20], id="skipped-holds"),
        pytest.param([[(10, REST)]], [10, 20], id="rest-advances"),
        pytest.param([[(10, DONE), (20, DONE)]], [10, 30], id="two-planned-in-one-day"),
        pytest.param([[(None, DONE)]], [10, 10], id="extra-session-holds"),
        pytest.param([[(30, DONE)]], [10, 10], id="out-of-order-holds"),
        pytest.param([[(10, DONE), (10, DONE)]], [10, 20], id="same-session-twice-once"),
    ],
)
def test_queue_scenarios(
    days: list[list[tuple[int | None, WorkoutStatus]]], expected: list[int]
) -> None:
    assert replay(days) == expected


def test_wraps_around_after_last_session() -> None:
    assert complete(ORDER, Position(70), 70, DONE) == Position(10)
    assert replay([[(t, DONE)] for t in ORDER]) == [*ORDER, 10]


def test_single_session_plan_cycles_to_itself() -> None:
    assert next_in_cycle([5], 5) == 5


@pytest.mark.parametrize(
    ("order", "current", "message"),
    [([], 1, "no sessions"), ([1, 2], 9, "not in the plan")],
)
def test_next_in_cycle_rejects_bad_input(order: list[int], current: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        next_in_cycle(order, current)


def test_upcoming_projects_the_week() -> None:
    assert upcoming(ORDER, Position(60), 4) == [60, 70, 10, 20]
    assert upcoming(ORDER, Position(10), 0) == []
    with pytest.raises(ValueError, match=">= 0"):
        upcoming(ORDER, Position(10), -1)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        # Spring forward: 2026-03-29 02:00 CET -> 03:00 CEST
        pytest.param(
            datetime(2026, 3, 28, 22, 59, tzinfo=UTC), date(2026, 3, 28), id="spring-before"
        ),
        pytest.param(
            datetime(2026, 3, 28, 23, 0, tzinfo=UTC), date(2026, 3, 29), id="spring-midnight"
        ),
        pytest.param(datetime(2026, 3, 29, 1, 30, tzinfo=UTC), date(2026, 3, 29), id="spring-gap"),
        pytest.param(
            datetime(2026, 3, 29, 21, 59, tzinfo=UTC), date(2026, 3, 29), id="spring-late"
        ),
        pytest.param(datetime(2026, 3, 29, 22, 0, tzinfo=UTC), date(2026, 3, 30), id="spring-next"),
        # Fall back: 2026-10-25 03:00 CEST -> 02:00 CET
        pytest.param(
            datetime(2026, 10, 24, 21, 59, tzinfo=UTC), date(2026, 10, 24), id="fall-before"
        ),
        pytest.param(
            datetime(2026, 10, 24, 22, 0, tzinfo=UTC), date(2026, 10, 25), id="fall-midnight"
        ),
        pytest.param(
            datetime(2026, 10, 25, 0, 30, tzinfo=UTC), date(2026, 10, 25), id="fall-repeat-hour"
        ),
        pytest.param(
            datetime(2026, 10, 25, 22, 59, tzinfo=UTC), date(2026, 10, 25), id="fall-late"
        ),
        pytest.param(datetime(2026, 10, 25, 23, 0, tzinfo=UTC), date(2026, 10, 26), id="fall-next"),
    ],
)
def test_local_date_across_dst(moment: datetime, expected: date) -> None:
    assert local_date(moment, BERLIN) == expected


def test_local_date_rejects_naive() -> None:
    with pytest.raises(ValueError, match="naive"):
        local_date(datetime(2026, 9, 30, 7, 30), BERLIN)  # noqa: DTZ001


# ---------------------------------------------------------------- swaps (ADR-0022)


def test_swap_with_next_exchanges_two_sessions_then_resumes() -> None:
    swapped = swap_with_next(ORDER, Position(10))
    assert swapped == Position(20, (10, 30))
    assert upcoming(ORDER, swapped, 5) == [20, 10, 30, 40, 50]


def test_swap_completes_like_any_session() -> None:
    position = swap_with_next(ORDER, Position(10))
    for template_id in (20, 10, 30):
        position = complete(ORDER, position, template_id, DONE)
    assert position == Position(40)


def test_skipping_holds_a_swapped_session() -> None:
    position = swap_with_next(ORDER, Position(10))
    assert complete(ORDER, position, 20, SKIPPED) == position
    assert complete(ORDER, position, 10, DONE) == position  # out of order: P waits its turn


def test_swapping_again_swaps_within_the_queue() -> None:
    twice = swap_with_next(ORDER, swap_with_next(ORDER, Position(10)))
    assert upcoming(ORDER, twice, 4) == [10, 20, 30, 40]


def test_swap_at_the_end_of_the_cycle_wraps() -> None:
    assert upcoming(ORDER, swap_with_next(ORDER, Position(70)), 3) == [10, 70, 20]


def test_swap_needs_two_sessions() -> None:
    with pytest.raises(ValueError, match="two sessions"):
        swap_with_next([5], Position(5))


def test_catching_up_points_after_the_session_logged_and_drops_any_swap() -> None:
    assert caught_up([1, 2, 3], 2) == Position(3)
    assert caught_up([1, 2, 3], 3) == Position(1)
