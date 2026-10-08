"""The "ready to progress" prompt in the bot (#13): shown after a save, answered by the owner
only, and checked again on every press."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from tests.bot.fakes import (
    OWNER,
    STRANGER,
    button_data,
    command,
    press,
    run,
    text_message,
    texts,
)
from training_coach.bot import progress as progress_ui
from training_coach.bot.messages import feedback_text, progress_text, saved_reply
from training_coach.db.models import Exercise, LadderStep, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.domain.records import NewBests
from training_coach.services import progress as progress_service
from training_coach.services import user_settings, users
from training_coach.services.progress import Feedback, Standing

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]


def _progress_buttons(calls: dict[str, list[dict[str, str]]]) -> list[str]:
    """The Saved reply's progress prompts, without the stretching choice (#98)."""
    return [d for d in button_data(calls["sendMessage"][0]) if d.startswith("p:")]


def _pull_up(sessions: Sessions) -> tuple[int, int]:
    """(exercise id, current step id) for Pull-up."""
    with sessions() as session:
        exercise = session.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
        state = users.exercise_state(session, exercise.id)
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
    assert _progress_buttons(calls) == [
        f"p:up:{exercise_id}:{step_id}",
        f"p:no:{exercise_id}:{step_id}",
    ]


async def test_a_save_below_the_rule_has_no_prompt(application: App, seeded: Sessions) -> None:
    calls = await _save(application, "pull-ups 8 7 6 6")
    (reply,) = texts(calls)
    assert "Ready to move up" not in reply
    assert _progress_buttons(calls) == []


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


async def test_a_feedback_bug_never_undoes_the_save(
    application: App, seeded: Sessions, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_session: Session, _workout_id: int, _tz: object = None) -> list[Feedback]:
        raise ValueError("a bug in feedback")

    monkeypatch.setattr(progress_service, "feedback", broken)
    with capture_logs() as logs:
        calls = await _save(application, "pull-ups 8 7 6 6")
    (reply,) = texts(calls)
    assert reply.startswith("Saved ")
    with seeded() as session:
        assert session.scalar(select(func.count()).select_from(Workout)) == 1
    assert {"event": "bot.feedback_failed", "error": "ValueError", "log_level": "error"} in logs


def test_a_long_saved_reply_fits_one_message() -> None:
    """The save has committed by then: a reply Telegram rejects would look like a failure."""
    many = [
        _feedback(
            exercise="X" * 120,
            kind=ExerciseKind.REPS,
            bests=NewBests(best_set=200, total=4000),
            status=Progress.READY,
            next_step="Y" * 120,
        )
        for _ in range(30)
    ]
    reply = saved_reply("Saved Torso: 30 exercises, 600 sets.", many)
    assert len(reply) <= 4096
    assert reply.startswith("Saved Torso")
    assert "more not shown" in reply
    assert saved_reply("Saved.", []) == "Saved."


async def test_progress_shows_each_exercise_and_offers_move_up(
    application: App, seeded: Sessions
) -> None:
    _top_session(seeded, days_ago=3)
    _top_session(seeded, days_ago=1)
    calls = await run(application, command("/progress", OWNER))
    (reply,) = texts(calls)
    assert reply.startswith("Progress: current step, last session, best set at this step")
    assert (
        "- Pull-up: Strict pull-up (2/4), last 12 / 12 / 12 / 12, best 12 reps. Ready to move up"
    ) in reply
    assert "- Dip (chairs): Feet on floor (1/3), not logged at this step yet" in reply
    exercise_id, step_id = _pull_up(seeded)
    assert button_data(calls["sendMessage"][0]) == [
        f"p:up:{exercise_id}:{step_id}",
        f"p:no:{exercise_id}:{step_id}",
    ]


async def test_progress_ignores_strangers(application: App) -> None:
    assert await run(application, command("/progress", STRANGER)) == {}


def _standing(**changes: object) -> Standing:
    base = Standing(
        exercise_id=1,
        exercise="Plank",
        kind=ExerciseKind.SECONDS,
        step_id=1,
        step="Front plank",
        step_number=1,
        steps=3,
        last=(45, 40),
        best_set=60,
        status=Progress.HOLD,
    )
    return Standing(**{**base.__dict__, **changes})  # type: ignore[arg-type]


def test_progress_text_units_and_limits() -> None:
    assert progress_text([]) == "No exercises in the plan yet."
    text = progress_text([_standing(), _standing(status=Progress.TOP_OF_LADDER)])
    assert "- Plank: Front plank (1/3), last 45s / 40s, best 60s" in text
    assert text.endswith("Top of the ladder")
    long = progress_text([_standing(exercise="X" * 120, step="Y" * 120)] * 40)
    assert len(long) <= 4096
    assert "more not shown" in long


def test_the_keyboard_stays_under_telegrams_button_limit() -> None:
    """More than 100 buttons and Telegram rejects the whole reply."""
    ready = [_standing(exercise_id=n, status=Progress.READY) for n in range(1, 61)]
    markup = progress_ui.keyboard(ready)
    assert markup is not None
    assert len(markup.inline_keyboard) == progress_ui.MAX_ROWS
    assert sum(len(row) for row in markup.inline_keyboard) <= 100
    assert progress_ui.keyboard([_standing()]) is None  # nothing ready, no buttons


def _strength_block(sessions: Sessions) -> None:
    with sessions() as session:
        user_settings.update(session, blocks=True, today=datetime.now(UTC).date())
        session.commit()


async def test_progress_holds_move_up_in_a_strength_block(
    application: App, seeded: Sessions
) -> None:
    """ADR-0028: moving up waits for the hypertrophy block."""
    _top_session(seeded, days_ago=3)
    _top_session(seeded, days_ago=1)
    _strength_block(seeded)
    calls = await run(application, command("/progress", OWNER))
    (reply,) = texts(calls)
    assert reply.endswith("Moving up waits for the hypertrophy block: this is a strength block.")
    assert button_data(calls["sendMessage"][0]) == []
    exercise_id, step_id = _pull_up(seeded)
    pressed = await run(application, press(f"p:up:{exercise_id}:{step_id}", OWNER))
    assert texts(pressed) == ["Pull-up waits for the hypertrophy block: this is a strength block."]
    assert _step_name(seeded) == "Strict pull-up"
