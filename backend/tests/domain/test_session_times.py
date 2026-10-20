"""Which set times from the phone are kept (ADR-0061)."""

from datetime import UTC, datetime, timedelta

import pytest

from training_coach.domain.session_times import MAX_AGE, SLACK, plausible

NOW = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
SET = timedelta(seconds=40)


@pytest.mark.parametrize(
    ("started", "done", "kept"),
    [
        (NOW - SET, NOW, True),
        (NOW, NOW, True),  # confirmed straight away
        (NOW - SET, NOW + SLACK, True),  # a phone a minute ahead
        (NOW - MAX_AGE, NOW - MAX_AGE + SET, True),  # resumed the next morning
        (NOW, NOW - SET, False),  # ends before it starts
        (NOW, NOW + SLACK + timedelta(seconds=1), False),  # in the future
        (NOW - MAX_AGE - timedelta(seconds=1), NOW, False),  # too long ago
    ],
)
def test_set_times_are_kept_only_when_plausible(
    started: datetime, done: datetime, kept: bool
) -> None:
    assert plausible(started, done, NOW) is kept
