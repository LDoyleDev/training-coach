from datetime import date

import pytest

from training_coach.bot.messages import (
    log_saved_text,
    rest_text,
    session_detail_text,
    today_text,
    week_text,
    work_list,
)
from training_coach.domain.blocks import Block, BlockKind
from training_coach.domain.enums import ExerciseKind
from training_coach.services.queue_actions import RestOutcome
from training_coach.services.today import Day, ItemPlan, SessionPlan, Today


def _item(
    kind: ExerciseKind,
    targets: tuple[int, ...],
    per_side: bool = False,
    *,
    name: str = "Plank",
    pair: int | None = None,
    baseline: bool = False,
) -> ItemPlan:
    return ItemPlan(name, kind, "Knees", None, per_side, targets, pair, baseline=baseline)


@pytest.mark.parametrize(
    ("item", "line"),
    [
        (_item(ExerciseKind.REPS, (8,)), "1. Plank (Knees): 8"),
        (_item(ExerciseKind.REPS, (10,), per_side=True), "1. Plank (Knees): 10 per side"),
        (_item(ExerciseKind.SECONDS, (30,)), "1. Plank (Knees): 30s"),
        (_item(ExerciseKind.DURATION_MIN, (45,)), "1. Plank (Knees): 45 min"),
    ],
)
def test_work_list_units(item: ItemPlan, line: str) -> None:
    assert work_list((item,)) == [line]


def test_work_list_alternates_pairs_with_a_gap_between_groups() -> None:
    items = (
        _item(ExerciseKind.REPS, (5, 6, 7), name="Pull-up", pair=1),
        _item(ExerciseKind.REPS, (10, 11), name="Dip", pair=1),
        _item(ExerciseKind.SECONDS, (30, 40), name="Hang"),
    )
    assert work_list(items) == [
        "1. Pull-up (Knees): 5",
        "2. Dip (Knees): 10",
        "3. Pull-up (Knees): 6",
        "4. Dip (Knees): 11",
        "5. Pull-up (Knees): 7",
        "",
        "6. Hang (Knees): 30s",
        "7. Hang (Knees): 40s",
    ]


def test_today_text_lists_exercises_and_notes() -> None:
    plan = Today(
        session=SessionPlan(7, "Arms", "Accessories", True, (_item(ExerciseKind.REPS, (8,)),)),
        logged_today=("Legs (done)",),
    )
    assert today_text(plan) == (
        "Today: Arms\nAccessories\nWarm up for about 10 minutes first.\n"
        "Stop if you feel sharp pain, dizziness or chest tightness.\n\n"
        "1. Plank (Knees): 8\n\n"
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


def test_session_detail_puts_cues_first_and_the_list_last() -> None:
    pull = ItemPlan("Pull-up", ExerciseKind.REPS, "Strict", "Full hang", False, (5, 5), 1)
    dip = ItemPlan("Dip", ExerciseKind.REPS, "Bars", None, False, (8, 8), 1)
    text = session_detail_text(SessionPlan(1, "Upper", "Strength", False, (pull, dip)))
    assert text.splitlines() == [
        "Upper: Strength",
        "",
        "How to do them:",
        "- Pull-up: Full hang",
        "",
        "Work down the list, alternating the two exercises of each pair.",
        "",
        "1. Pull-up (Strict): 5",
        "2. Dip (Bars): 8",
        "3. Pull-up (Strict): 5",
        "4. Dip (Bars): 8",
        "",
        "Copy the list, put in what you did and send it back to log it.",
    ]


def test_session_detail_without_pairs_or_cues() -> None:
    text = session_detail_text(
        SessionPlan(2, "Zone 2", "Easy", False, (_item(ExerciseKind.DURATION_MIN, (45,)),))
    )
    assert "How to do them:" not in text
    assert "Work down the list.\n\n1. Plank (Knees): 45 min" in text


@pytest.mark.parametrize(
    ("advanced", "text"),
    [
        (True, "Arms logged as a rest day. Enjoy it."),
        (False, "Rest today. Arms moves to tomorrow and the rest of the week shifts a day."),
    ],
)
def test_rest_text(advanced: bool, text: str) -> None:
    assert rest_text(RestOutcome("Arms", advanced)) == text


def test_saved_text_says_one_set_not_one_sets() -> None:
    assert log_saved_text(1, 1, "Long zone 2", None) == "Saved Long zone 2: 1 exercise, 1 set."
    assert (
        log_saved_text(2, 1, "Torso", "Arms") == "Saved Torso: 1 exercise, 2 sets. Next up: Arms."
    )


def test_baseline_exercises_are_named_once_above_the_list() -> None:
    items = (
        _item(ExerciseKind.REPS, (5,), name="Pull-up", baseline=True),
        _item(ExerciseKind.REPS, (8,), name="Dip"),
        _item(ExerciseKind.SECONDS, (30,), name="Hang", baseline=True),
    )
    plan = SessionPlan(1, "Torso", "Pull", False, items)
    text = today_text(Today(plan, ()))
    assert "Baseline for Pull-up and Hang: the first session at this step." in text
    assert text.index("Baseline") < text.index("1. Pull-up")
    assert "Baseline for Pull-up and Hang" in session_detail_text(plan)
    # The list itself is untouched, so it still reads back as a log.
    assert "1. Pull-up (Knees): 5" in text


def test_no_baseline_line_once_every_exercise_has_history() -> None:
    plan = SessionPlan(1, "Torso", "Pull", False, (_item(ExerciseKind.REPS, (5,)),))
    assert "Baseline" not in today_text(Today(plan, ()))
    assert "Baseline" not in session_detail_text(plan)


def test_every_session_carries_the_stop_reminder_even_without_a_warm_up() -> None:
    items = (_item(ExerciseKind.DURATION_MIN, (45,)),)
    plan = SessionPlan(9, "Long zone 2", "Easy", False, items, kind="conditioning")
    text = today_text(Today(plan, ()))
    assert "Warm up" not in text
    assert "Stop if you feel sharp pain, dizziness or chest tightness." in text
