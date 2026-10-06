from datetime import date

import pytest

from training_coach.bot.messages import targets_text, today_text, week_text
from training_coach.domain.enums import ExerciseKind
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
        session=SessionPlan("Arms", "Accessories", True, (_item(ExerciseKind.REPS, (8,)),)),
        logged_today=("Legs (done)",),
    )
    assert today_text(plan) == (
        "Today: Arms\nAccessories\n\n- Plank (Knees): 8\n\n"
        "This one is optional: resting today is fine.\n\nAlready logged today: Legs (done)"
    )


def test_week_text() -> None:
    text = week_text([Day(date(2026, 10, 6), "Legs"), Day(date(2026, 10, 7), "Zone 2")])
    assert text.splitlines()[2:] == ["Tue 06 Oct  Legs", "Wed 07 Oct  Zone 2"]
