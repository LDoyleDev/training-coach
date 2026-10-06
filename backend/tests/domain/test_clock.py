from datetime import time

import pytest

from training_coach.domain.clock import parse_hhmm


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("07:30", time(7, 30)),
        ("7:30", time(7, 30)),
        (" 6.45 ", time(6, 45)),
        ("00:00", time(0, 0)),
        ("23:59", time(23, 59)),
        ("24:00", None),
        ("12:60", None),
        ("7:3", None),
        ("0730", None),
        ("7:30pm", None),
        ("", None),
        ("half seven", None),
    ],
)
def test_parse_hhmm(text: str, expected: time | None) -> None:
    assert parse_hhmm(text) == expected
