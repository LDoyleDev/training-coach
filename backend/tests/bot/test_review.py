"""/review and the weekly review text (#73)."""

from datetime import date

from telegram.ext import Application

from tests.bot.fakes import OWNER, STRANGER, command, run, texts
from training_coach.bot.messages import review_text
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.records import NewBests
from training_coach.services.review import Best, Review

App = Application  # type: ignore[type-arg]  # see build_bot


def _review(**changes: object) -> Review:
    base = Review(
        start=date(2026, 10, 5),
        planned=7,
        done=0,
        rested=0,
        extras=0,
        volume=[],
        bests=[],
        ready=[],
    )
    return Review(**{**base.__dict__, **changes})  # type: ignore[arg-type]


def test_an_empty_week_says_so() -> None:
    assert review_text(_review()) == (
        "Week of Mon 05 Oct\n\nSessions: 0 of 7 done.\n\nNo sets logged this week."
    )


def test_a_full_review() -> None:
    text = review_text(
        _review(
            done=5,
            rested=2,
            extras=1,
            volume=[("quads", 24), ("lats", 12), ("biceps", 6)],
            bests=[
                Best(
                    "Pull-up", "Strict pull-up", ExerciseKind.REPS, NewBests(best_set=12, total=44)
                )
            ],
            ready=["Pull-up", "Dip (chairs)"],
        )
    )
    assert "Sessions: 5 of 7 done (2 rest days, 1 extra)." in text
    assert "Hard sets per muscle (aim 10-20):" in text
    assert "- quads: 24 (high)" in text
    assert "- lats: 12\n" in text
    assert "- biceps: 6 (low)" in text
    assert "- Pull-up (Strict pull-up): 12 reps in one set and 44 reps in total" in text
    assert text.endswith("Ready to move up: Pull-up, Dip (chairs). See /progress.")


def test_one_rest_day_and_a_total_only_best() -> None:
    text = review_text(
        _review(
            rested=1,
            bests=[Best("Plank", "Front plank", ExerciseKind.SECONDS, NewBests(total=150))],
        )
    )
    assert "(1 rest day)" in text
    assert "- Plank (Front plank): 150s in total" in text


def test_a_long_review_fits_one_message() -> None:
    text = review_text(_review(volume=[("x" * 200, 12)] * 40))
    assert len(text) <= 4096
    assert "more not shown" in text


async def test_review_answers_the_owner_only(application: App) -> None:
    (reply,) = texts(await run(application, command("/review", OWNER)))
    assert reply.startswith("Week of ")
    assert "Sessions: 0 of 7 done." in reply
    assert await run(application, command("/review", STRANGER)) == {}


def test_in_a_strength_block_moving_up_waits_and_strength_bests_say_so() -> None:
    text = review_text(
        _review(
            strength_block=True,
            ready=["Pull-up"],
            bests=[
                Best(
                    "Pull-up",
                    "Pause at top",
                    ExerciseKind.REPS,
                    NewBests(best_set=6),
                    strength=True,
                )
            ],
        )
    )
    assert "- Pull-up (Pause at top, strength block): 6 reps in one set" in text
    assert text.endswith("Ready to move up when the hypertrophy block starts: Pull-up.")
