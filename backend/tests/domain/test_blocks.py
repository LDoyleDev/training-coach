from datetime import date, timedelta

import pytest

from training_coach.domain.blocks import Block, BlockKind, block_on, paused_days

START = date(2026, 10, 5)  # a Monday


def day(n: int) -> date:
    return START + timedelta(days=n)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        pytest.param(-1, None, id="before-blocks"),
        pytest.param(0, Block(1, BlockKind.STRENGTH, 1), id="first-day"),
        pytest.param(6, Block(1, BlockKind.STRENGTH, 1), id="end-of-week-1"),
        pytest.param(7, Block(1, BlockKind.STRENGTH, 2), id="week-2"),
        pytest.param(27, Block(1, BlockKind.STRENGTH, 4), id="last-day-of-block-1"),
        pytest.param(28, Block(2, BlockKind.HYPERTROPHY, 1), id="hypertrophy-next"),
        pytest.param(56, Block(3, BlockKind.STRENGTH, 1), id="and-back-to-strength"),
    ],
)
def test_four_week_blocks_alternate_from_strength(offset: int, expected: Block | None) -> None:
    assert block_on(day(offset), START) == expected


def test_paused_days_dont_count() -> None:
    week_off = {day(n) for n in range(7, 14)}
    assert block_on(day(28), START, week_off) == Block(1, BlockKind.STRENGTH, 4)
    assert block_on(day(35), START, week_off) == Block(2, BlockKind.HYPERTROPHY, 1)


def test_pause_and_resume() -> None:
    changes = [(day(3), True), (day(5), False)]
    assert paused_days(changes, until=day(10)) == {day(3), day(4)}


def test_still_paused_runs_until_today() -> None:
    assert paused_days([(day(3), True)], until=day(5)) == {day(3), day(4), day(5)}


def test_repeated_changes_change_nothing() -> None:
    changes = [(day(1), False), (day(3), True), (day(4), True), (day(5), False), (day(6), False)]
    assert paused_days(changes, until=day(10)) == {day(3), day(4)}


def test_no_changes_no_pause() -> None:
    assert paused_days([], until=day(10)) == set()
