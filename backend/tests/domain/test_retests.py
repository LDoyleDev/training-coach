from datetime import date, timedelta

import pytest

from training_coach.domain.retests import PastTest, block_start, due, name

D = date(2026, 11, 2)


def days(n: int) -> timedelta:
    return timedelta(days=n)


# ------------------------------------------------------------------ the 4-week cadence (blocks off)


def test_nothing_is_due_until_the_baseline_is_started() -> None:
    assert due(D, [], None) is None
    assert due(D, [], D) is None  # with blocks on too


def test_day_2_follows_on_a_later_day() -> None:
    done = [PastTest(D, 1)]
    assert due(D, done, None) is None  # not the same day
    assert due(D + days(1), done, None) == 2
    assert due(D + days(5), done, None) == 2  # waits until it's done


def test_a_complete_round_is_due_again_four_weeks_after_its_day_1() -> None:
    done = [PastTest(D, 1), PastTest(D + days(1), 2)]
    assert due(D + days(1), done, None) is None
    assert due(D + days(27), done, None) is None
    assert due(D + days(28), done, None) == 1
    assert due(D + days(29), [*done, PastTest(D + days(28), 1)], None) == 2


def test_days_after_the_one_asked_about_are_ignored() -> None:
    """The week ahead asks about future days one at a time, with what it planned so far."""
    done = [PastTest(D - days(40), 1), PastTest(D - days(39), 2), PastTest(D + days(1), 1)]
    assert due(D, done, None) == 1  # the future day 1 isn't done yet on D


# ------------------------------------------------------------------ blocks on


def test_a_round_is_due_from_each_block_start() -> None:
    start = D
    old = [PastTest(start - days(30), 1), PastTest(start - days(29), 2)]
    assert due(start + days(3), old, start) == 1  # a round from the last block doesn't count
    this = [*old, PastTest(start + days(3), 1)]
    assert due(start + days(4), this, start) == 2
    assert due(start + days(20), [*this, PastTest(start + days(4), 2)], start) is None


# ------------------------------------------------------------------ block starts and names


def test_block_start_counts_blocks_from_the_day_blocks_began() -> None:
    assert block_start(D - days(1), D) is None
    assert block_start(D, D) == D
    assert block_start(D + days(27), D) == D
    assert block_start(D + days(28), D) == D + days(28)
    assert block_start(D + days(60), D) == D + days(56)


def test_paused_days_push_the_next_block_start_back() -> None:
    paused = {D + days(n) for n in range(3, 10)}  # a week off
    assert block_start(D + days(30), D, paused) == D
    assert block_start(D + days(35), D, paused) == D + days(35)


@pytest.mark.parametrize(
    ("done", "expected"),
    [
        ([], "Baseline tests, day 1"),
        ([PastTest(D, 1)], "Baseline tests, day 1"),
        ([PastTest(D, 1), PastTest(D + days(1), 2)], "Retest, day 1"),
    ],
)
def test_the_first_round_is_the_baseline(done: list[PastTest], expected: str) -> None:
    assert name(1, done) == expected


def test_a_block_that_starts_while_paused_brings_its_retest_once_training_resumes() -> None:
    paused = {D + days(n) for n in range(28, 40)}  # paused from the day block 2 starts
    start = block_start(D + days(45), D, paused)
    assert start == D + days(28)  # after 28 counted days, on a paused day
    old = [PastTest(D, 1), PastTest(D + days(1), 2)]
    assert due(D + days(40), old, start) == 1  # due on the first day back
