from datetime import date

import pytest

from training_coach.bot.messages import (
    rest_text,
    session_detail_text,
    targets_text,
    today_text,
    week_text,
)
from training_coach.domain.blocks import Block, BlockKind
from training_coach.domain.enums import ExerciseKind
from training_coach.services.queue_actions import RestOutcome
from training_coach.services.today import Day, ItemPlan, SessionPlan, Today


def _item(kind: ExerciseKind, targets: tuple[int, ...], per_side: bool = False) -> ItemPlan:
    return ItemPlan("Plank", kind, "Knees", None, per_side, targets)


@pytest.mark.parametrize(
    ("item", "text"),
    [
        (_item(ExerciseKind.REPS, (8, 8, 7)), "8 / 8 / 7"),
        (_item(ExerciseKind.REPS, (10, 10), per_side=True), "10 / 10 per side"),
        (_item(ExerciseKind.SECONDS, (30, 30)), "30s / 30s"),
        (_item(ExerciseKind.DURATION_MIN, (45,)), "45 min"),
    ],
)
def test_targets_text(item: ItemPlan, text: str) -> None:
    assert targets_text(item) == text


def test_today_text_lists_exercises_and_notes() -> None:
    plan = Today(
        session=SessionPlan(7, "Arms", "Accessories", True, (_item(ExerciseKind.REPS, (8,)),)),
        logged_today=("Legs (done)",),
    )
    assert today_text(plan) == (
        "Today: Arms\nAccessories\nWarm up for about 10 minutes first.\n\n"
        "- Plank (Knees): 8\n\n"
        "This one is optional: resting today is fine.\n\nAlready logged today: Legs (done)"
    )


def test_today_text_names_the_block_and_skips_warm_up_for_cardio() -> None:
    cardio = SessionPlan(4, "Zone 2", "Easy", False, (), kind="conditioning")
    in_block = Today(session=cardio, logged_today=(), block=Block(2, BlockKind.HYPERTROPHY, 3))
    assert today_text(in_block).splitlines()[:3] == [
        "Today: Zone 2",
        "Easy",
        "Week 3 of 4, hypertrophy block.",
    ]
    assert "Warm up" not in today_text(in_block)


def test_week_text() -> None:
    text = week_text([Day(date(2026, 10, 6), "Legs"), Day(date(2026, 10, 7), "Zone 2")])
    assert text.splitlines()[2:] == ["Tue 06 Oct  Legs", "Wed 07 Oct  Zone 2"]


def test_session_detail_includes_cues() -> None:
    item = ItemPlan("Pull-up", ExerciseKind.REPS, "Strict", "Full hang at the bottom", False, (5,))
    text = session_detail_text(SessionPlan(1, "Upper", "Strength", False, (item,)))
    assert text.splitlines()[2:4] == ["- Pull-up (Strict): 5", "  Full hang at the bottom"]


@pytest.mark.parametrize(
    ("advanced", "text"),
    [
        (True, "Arms logged as a rest day. Enjoy it."),
        (False, "Rest today. Arms moves to tomorrow and the rest of the week shifts a day."),
    ],
)
def test_rest_text(advanced: bool, text: str) -> None:
    assert rest_text(RestOutcome("Arms", advanced)) == text
