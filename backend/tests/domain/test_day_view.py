"""Grouping a day's set logs for Today's day view (ADR-0068)."""

from training_coach.domain.day_view import LoggedExercise, LoggedSet, group


def test_sets_group_per_exercise_in_the_order_done() -> None:
    rows = [
        (2, 20, 1, "both", 15),
        (3, 30, 1, "left", 12),
        (3, 30, 1, "right", 11),
        (2, 20, 2, "both", 14),
        (3, 30, 2, "left", 10),
        (3, 30, 2, "right", 10),
    ]
    assert group(rows) == (
        LoggedExercise(2, 20, (LoggedSet(1, 15), LoggedSet(2, 14))),
        LoggedExercise(3, 30, (LoggedSet(1, 12, 11), LoggedSet(2, 10, 10))),
    )


def test_another_step_of_the_same_exercise_is_its_own_line() -> None:
    rows = [(1, 10, 1, "both", 8), (1, 11, 1, "both", 5)]
    assert group(rows) == (
        LoggedExercise(1, 10, (LoggedSet(1, 8),)),
        LoggedExercise(1, 11, (LoggedSet(1, 5),)),
    )


def test_one_side_logged_alone_shows_on_the_left() -> None:
    assert group([(1, 10, 1, "right", 9)]) == (LoggedExercise(1, 10, (LoggedSet(1, 9),)),)
    assert group([(1, 10, 1, "left", 9)]) == (LoggedExercise(1, 10, (LoggedSet(1, 9),)),)


def test_sets_sort_by_number_and_nothing_logged_is_empty() -> None:
    rows = [(1, 10, 2, "both", 6), (1, 10, 1, "both", 7)]
    assert group(rows)[0].sets == (LoggedSet(1, 7), LoggedSet(2, 6))
    assert group([]) == ()
