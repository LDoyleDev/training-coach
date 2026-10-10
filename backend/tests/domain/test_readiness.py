from datetime import UTC, datetime, timedelta

import pytest

from training_coach.domain.readiness import (
    DOCTOR_NOTE,
    DUE_NOTE,
    KEYS,
    QUESTIONS,
    RENEW,
    VERSION,
    Status,
    note,
    status,
)

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
ALL_NO = dict.fromkeys(KEYS, False)


def test_the_questions_have_unique_keys_and_are_questions() -> None:
    assert len(KEYS) == len(QUESTIONS) == 7
    assert all(q.text.endswith("?") for q in QUESTIONS)


def test_all_no_is_clear_and_any_yes_means_see_a_doctor() -> None:
    assert status(ALL_NO, VERSION, NOW, NOW) is Status.CLEAR
    assert status({**ALL_NO, "joints": True}, VERSION, NOW, NOW) is Status.SEE_DOCTOR


@pytest.mark.parametrize(
    ("answers", "version", "answered"),
    [
        (None, None, None),  # never answered
        (ALL_NO, VERSION, NOW - RENEW - timedelta(seconds=1)),  # about 6 months ago
        (ALL_NO, VERSION - 1, NOW),  # the questions changed since
    ],
)
def test_answers_that_no_longer_count_are_due_again(
    answers: dict[str, bool] | None, version: int | None, answered: datetime | None
) -> None:
    assert status(answers, version, answered, NOW) is Status.DUE


def test_answers_still_count_on_the_last_day() -> None:
    assert status(ALL_NO, VERSION, NOW - RENEW, NOW) is Status.CLEAR


@pytest.mark.parametrize(
    ("current", "hard", "expected"),
    [
        (Status.SEE_DOCTOR, True, DOCTOR_NOTE),
        (Status.DUE, True, DUE_NOTE),
        (Status.CLEAR, True, None),
        (Status.SEE_DOCTOR, False, None),  # an easy day: nothing to say
        (Status.DUE, False, None),
    ],
)
def test_today_says_something_only_on_hard_days(
    current: Status, hard: bool, expected: str | None
) -> None:
    assert note(current, hard) == expected
