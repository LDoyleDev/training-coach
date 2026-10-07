"""The "ready to progress" prompt in the bot (#13): shown after a save, answered by the owner
only, and checked again on every press."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, button_data, press, run, text_message, texts
from training_coach.bot import progress as progress_ui
from training_coach.bot.messages import feedback_text
from training_coach.db.models import Exercise, ExerciseState, LadderStep, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.services.progress import Feedback

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _pull_up(sessions: Sessions) -> tuple[int, int]:
    """(exercise id, current step id) for Pull-up."""
    with sessions() as session:
        exercise = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
        state = session.get(ExerciseState, exercise.id)
        assert state is not None
        return exercise.id, state.ladder_step_id


def _top_session(sessions: Sessions, days_ago: int) -> None:
    exercise_id, step_id = _pull_up(sessions)
    with sessions() as session:
        workout = Workout(
            local_date=datetime.now(UTC).date() - timedelta(days=days_ago),
            template_id=None,
            status=WorkoutStatus.DONE,
        )
        workout.sets = [
            SetLog(
                exercise_id=exercise_id, ladder_step_id=step_id, set_no=n, side=Side.BOTH, value=12
            )
            for n in range(1, 5)
        ]
        session.add(workout)
        session.commit()


def _step_name(sessions: Sessions) -> str:
    _, step_id = _pull_up(sessions)
    with sessions() as session:
        step = session.get(LadderStep, step_id)
        assert step is not None
        return step.name


async def _save(application: App, text: str) -> dict[str, list[dict[str, str]]]:
    shown = await run(application, text_message(text, OWNER))
    token = button_data(shown["sendMessage"][0])[0].split(":")[2]
    return await run(application, press(f"l:save:{token}", OWNER))


async def test_a_save_that_meets_the_rule_offers_to_move_up(
    application: App, seeded: Sessions
) -> None:
    _top_session(seeded, days_ago=3)
    calls = await _save(application, "pull-ups 12 12 12 12")
    (reply,) = texts(calls)
    assert reply.startswith("Saved ")
    assert (
        "Pull-up: top of the range two sessions running. Ready to move up to Pause at top?" in reply
    )
    exercise_id, step_id = _pull_up(seeded)
    assert button_data(calls["sendMessage"][0]) == [
        f"p:up:{exercise_id}:{step_id}",
        f"p:no:{exercise_id}:{step_id}",
    ]


async def test_a_save_below_the_rule_has_no_prompt(application: App, seeded: Sessions) -> None:
    calls = await _save(application, "pull-ups 8 7 6 6")
    (reply,) = texts(calls)
    assert "Ready to move up" not in reply
    assert button_data(calls["sendMessage"][0]) == []


async def test_move_up_moves_the_exercise(application: App, seeded: Sessions) -> None:
    _top_session(seeded, days_ago=3)
    _top_session(seeded, days_ago=1)
    exercise_id, step_id = _pull_up(seeded)
    calls = await run(application, press(f"p:up:{exercise_id}:{step_id}", OWNER))
    assert texts(calls) == [
        "Moved up: Pull-up is now Pause at top. Targets start again at the bottom of the range."
    ]
    assert _step_name(seeded) == "Pause at top"
    # A second tap on the same old prompt changes nothing.
    again = await run(application, press(f"p:up:{exercise_id}:{step_id}", OWNER))
    assert texts(again) == ["Pull-up has already moved on since that message."]
    assert _step_name(seeded) == "Pause at top"


async def test_not_yet_stays(application: App, seeded: Sessions) -> None:
    exercise_id, step_id = _pull_up(seeded)
    calls = await run(application, press(f"p:no:{exercise_id}:{step_id}", OWNER))
    assert texts(calls) == [
        "Staying on Pull-up (Strict pull-up). I'll ask again after your next session at the top "
        "of the range."
    ]
    assert _step_name(seeded) == "Strict pull-up"


async def test_a_forged_press_for_an_unready_exercise_changes_nothing(
    application: App, seeded: Sessions
) -> None:
    exercise_id, step_id = _pull_up(seeded)
    calls = await run(application, press(f"p:up:{exercise_id}:{step_id}", OWNER))
    assert texts(calls) == ["Pull-up doesn't meet the rule any more. Keep going."]
    assert _step_name(seeded) == "Strict pull-up"


@pytest.mark.parametrize("action", ["up", "no"])
async def test_strangers_get_nothing(application: App, seeded: Sessions, action: str) -> None:
    """Threat model T1: no answer, no reply, no change."""
    _top_session(seeded, days_ago=3)
    _top_session(seeded, days_ago=1)
    exercise_id, step_id = _pull_up(seeded)
    calls = await run(application, press(f"p:{action}:{exercise_id}:{step_id}", STRANGER))
    assert calls == {}
    assert _step_name(seeded) == "Strict pull-up"


async def test_unknown_ids_get_a_plain_answer(application: App) -> None:
    calls = await run(application, press("p:up:999:999", OWNER))
    assert texts(calls) == ["That exercise isn't in the plan any more."]
    calls = await run(application, press("p:no:999:999", OWNER))
    assert texts(calls) == ["That exercise isn't in the plan any more."]


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "p:up:1",
        "p:jump:1:2",
        "x:up:1:2",
        "p:up:a:2",
        "p:up:0:2",
        "p:up:1:-2",
        f"p:up:{2**63}:1",
        "p:up:1:2:3",
        f"p:up:{chr(0xFF11)}:2",  # a full-width 1: decimal to Python, not to us
    ],
)
def test_parse_rejects_anything_else(data: str | None) -> None:
    assert progress_ui.parse(data) is None


def test_parse_reads_a_press() -> None:
    assert progress_ui.parse("p:no:3:17") == progress_ui.Press("no", 3, 17)


def test_answering_one_prompt_keeps_the_others() -> None:
    def row(exercise: int) -> list[InlineKeyboardButton]:
        return [
            InlineKeyboardButton("Move up", callback_data=f"p:up:{exercise}:5"),
            InlineKeyboardButton("Not yet", callback_data=f"p:no:{exercise}:5"),
        ]

    markup = InlineKeyboardMarkup([row(1), row(2)])
    left = progress_ui._without(markup, progress_ui.Press("up", 1, 5))
    assert left is not None
    assert [b.callback_data for r in left.inline_keyboard for b in r] == ["p:up:2:5", "p:no:2:5"]
    assert progress_ui._without(left, progress_ui.Press("no", 2, 5)) is None
    assert progress_ui._without(None, progress_ui.Press("no", 2, 5)) is None


def _feedback(**changes: object) -> Feedback:
    base = Feedback(
        exercise_id=1,
        exercise="Plank",
        kind=ExerciseKind.SECONDS,
        step_id=1,
        bests=NewBests(),
        status=Progress.HOLD,
        next_step=None,
        note_top=False,
    )
    return Feedback(**{**base.__dict__, **changes})  # type: ignore[arg-type]


def test_feedback_text_units_and_cases() -> None:
    assert feedback_text([_feedback()]) == ""
    assert feedback_text([_feedback(bests=NewBests(best_set=45, total=120))]) == (
        "New best on Plank: 45s in one set and 120s in total."
    )
    walk = _feedback(exercise="Walk", kind=ExerciseKind.DURATION_MIN, bests=NewBests(total=40))
    assert feedback_text([walk]) == "New best on Walk: 40 min in total."
    one = _feedback(exercise="Pistol", kind=ExerciseKind.REPS, bests=NewBests(best_set=1))
    assert feedback_text([one]) == "New best on Pistol: 1 rep in one set."
    top = _feedback(exercise="Dip", status=Progress.TOP_OF_LADDER, note_top=True)
    assert "last step in your plan" in feedback_text([top])
    quiet = _feedback(exercise="Dip", status=Progress.TOP_OF_LADDER, note_top=False)
    assert feedback_text([quiet]) == ""
