from datetime import date

import pytest

from training_coach.domain.dates import DateLine, date_line

THU = date(2026, 10, 8)  # a Thursday


@pytest.mark.parametrize(
    ("line", "day", "rest"),
    [
        ("yesterday", date(2026, 10, 7), ""),
        ("Yesterday: Legs", date(2026, 10, 7), "Legs"),
        ("Tue", date(2026, 10, 6), ""),
        ("tuesday rest", date(2026, 10, 6), "rest"),
        ("Thu", date(2026, 10, 1), ""),  # today's weekday means a week ago
        ("29/9", date(2026, 9, 29), ""),
        ("30 Sep Legs", date(2026, 9, 30), "Legs"),
        ("Wed 30th September - Day 1 Legs", date(2026, 9, 30), "Day 1 Legs"),
        ("Mon, 5 Oct: Arms", date(2026, 10, 5), "Arms"),
        ("2026-09-29", date(2026, 9, 29), ""),
        ("8 Oct", THU, ""),  # today: the caller treats it as an ordinary log
    ],
)
def test_reads_a_date_and_keeps_the_rest_of_the_line(line: str, day: date, rest: str) -> None:
    assert date_line(line, THU) == DateLine(day, rest)


def test_a_dash_after_the_date_is_dropped() -> None:
    line = "Wed 30 Sep " + chr(0x2014) + " Legs"
    assert date_line(line, THU) == DateLine(date(2026, 9, 30), "Legs")


@pytest.mark.parametrize(
    "line",
    [
        "pull-ups 8 8 7",
        "8/8/7",
        "12 12 12",
        "Tibialis raise: 20",
        "",
        "monkey bars 5",
        "Sun salutation 5",
        "20 pushups 3",
        "3 sets pull ups",
        "Mon 5 pull-ups",
        "30 Foo",
    ],
)
def test_a_log_line_is_not_a_date(line: str) -> None:
    assert date_line(line, THU) is None


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ("Tue 30 Sep", "30 Sep was a Wednesday"),
        ("31/2", "isn't a date I can read"),
        ("29/13", "isn't a date I can read"),
        ("2026-02-30", "isn't a date I can read"),
        ("2026-10-09", "hasn't happened yet"),
        ("20 Sep", "more than 14 days ago"),
    ],
)
def test_a_date_that_cannot_be_used_is_a_problem(line: str, problem: str) -> None:
    result = date_line(line, THU)
    assert isinstance(result, str)
    assert problem in result


def test_early_january_reads_last_december() -> None:
    assert date_line("30 Dec", date(2027, 1, 3)) == DateLine(date(2026, 12, 30), "")
    assert date_line("29/2", date(2027, 3, 1)) == "'29/2' isn't a date I can read"
