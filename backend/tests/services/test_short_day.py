"""Short on time today (ADR-0082): the day's length, the trimmed guided session, and what a
shorter day saves (ADR-0084), against the bundled plan."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import Place, Side, WorkoutStatus
from training_coach.domain.trim import WarmUp
from training_coach.services import guided, user_settings, users, workout_log
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
LEGS = (
    "jump-squat",
    "tibialis-raise",
    "kb-swing",
    "calf-raise",
    "bulgarian-split-squat",
    "hamstring-curl",
    "pistol-squat",
    "single-leg-rdl",
)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _at(session: Session, slug: str) -> None:
    template = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id = template.id
    session.flush()


def _today(session: Session) -> guided.Guided:
    found = guided.today(session, DAY, BERLIN)
    assert found is not None
    return found


def _choose(
    session: Session, minutes: int | None, keep: tuple[str, ...] = (), revision: int | None = None
) -> guided.Guided:
    kept = guided.kept(session, DAY)
    seen = revision if revision is not None else (kept.revision if kept is not None else 0)
    assert isinstance(guided.choose_length(session, _today(session), seen, minutes, keep), int)
    return _today(session)


def _sets(found: guided.Guided) -> dict[str, int]:
    return {item.slug: len(item.targets) for item in found.items}


@pytest.mark.parametrize(
    ("minutes", "sets", "dropped", "warm_up"),
    [
        (None, (3, 3, 3, 4, 3, 3, 3, 3), (), WarmUp.FULL),
        (40, (2,) * 8, (), WarmUp.FULL),  # every exercise keeps two sets
        (30, (2,) * 8, (), WarmUp.RAMP),  # ramp sets replace the 5-minute warm-up
        (
            20,
            (2, 0, 2, 0, 2, 0, 0, 0),
            ("hamstring-curl", "calf-raise", "tibialis-raise", "pistol-squat", "single-leg-rdl"),
            WarmUp.RAMP,
        ),
    ],
)
def test_a_home_legs_day_fits_the_minutes_chosen(
    plan: Session,
    minutes: int | None,
    sets: tuple[int, ...],
    dropped: tuple[str, ...],
    warm_up: WarmUp,
) -> None:
    found = _choose(plan, minutes)
    length = found.length
    assert length is not None
    assert tuple(item.slug for item in found.items) == LEGS  # nothing removed: indexes stay
    assert tuple(_sets(found).values()) == sets
    assert tuple(found.items[i].slug for i in length.trimmed.dropped) == dropped
    assert length.trimmed.warm_up is warm_up
    assert found.warm_up is (warm_up is WarmUp.FULL)
    assert found.minutes == length.trimmed.minutes
    assert minutes is None or found.minutes <= minutes
    assert (length.minutes, length.planned, length.trimmed.fits) == (minutes, 49, True)
    assert len(found.order) == sum(sets)  # a dropped exercise has no sets in the order
    assert all(s.target == found.items[s.item].targets[s.set_no - 1] for s in found.order)


def test_a_pair_whose_partner_is_dropped_is_done_straight(plan: Session) -> None:
    found = _choose(plan, 20)
    jump = [s for s in found.order if found.items[s.item].slug == "jump-squat"]
    assert [s.set_no for s in jump] == [1, 2]  # tibialis raise, its partner, is dropped
    assert not any(s.rest.switch for s in jump)
    assert jump[0].rest.seconds == 90  # a compound done on its own (ADR-0065)


def test_an_exercise_kept_for_the_day_is_never_dropped(plan: Session) -> None:
    found = _choose(plan, 20, ("hamstring-curl",))
    length = found.length
    assert length is not None
    assert length.keep == ("hamstring-curl",)
    assert _sets(found)["hamstring-curl"] == 2
    assert "hamstring-curl" not in {found.items[i].slug for i in length.trimmed.dropped}


def test_a_conditioning_session_shortens_its_cardio_first_and_has_no_warm_up(
    plan: Session,
) -> None:
    _at(plan, "moderate-cardio")
    found = _choose(plan, 30)
    length = found.length
    assert length is not None
    assert length.trimmed.warm_up is WarmUp.NONE
    assert found.items[0].slug == "moderate-cardio"
    assert found.items[0].targets == (10,)  # 30 minutes as planned, never below 10
    assert length.trimmed.dropped == ()
    assert found.minutes <= 30


def test_a_recovery_session_runs_as_planned(plan: Session) -> None:
    _at(plan, "recovery")
    found = _today(plan)
    assert found.length is None
    assert guided.choose_length(plan, found, 0, 20, ()) == guided.NOT_TRIMMED
    assert guided.kept(plan, DAY) is None  # nothing written


def test_a_strength_block_prescribes_first_then_the_trim(plan: Session) -> None:
    """Neck flexion is planned at 2 sets; a strength block raises it to 3 (ADR-0028), and a
    40-minute day takes every exercise back to two."""
    user_settings.update(plan, blocks=True, today=DAY)
    _at(plan, "torso")
    assert _sets(_today(plan))["neck-flexion"] == 3
    found = _choose(plan, 40)
    assert found.block is not None
    assert max(_sets(found).values()) == 2


def test_the_length_is_fixed_once_the_first_set_is_kept(plan: Session) -> None:
    found = _choose(plan, 20)
    assert guided.keep(plan, found, 2, 1, [], [guided.Done(0, 1, 6)]) == 3
    assert guided.choose_length(plan, _today(plan), 3, 40, ()) == guided.STARTED
    again = _today(plan)
    assert again.length is not None
    assert (again.length.minutes, again.length.fixed) == (20, True)
    assert _sets(again) == _sets(found)


def test_a_fixed_length_does_not_move_with_the_persons_pace(plan: Session) -> None:
    found = _choose(plan, 30)
    assert guided.keep(plan, found, 2, 1, [], [guided.Done(0, 1, 6)]) == 3
    _timed_legs(plan, minutes=66, times=3)  # much slower than estimated, after the start
    again = _today(plan)
    assert again.length is not None
    assert again.length.pace == 1.0
    assert _sets(again) == _sets(found)


def test_a_set_the_trim_dropped_is_refused(plan: Session) -> None:
    found = _choose(plan, 20)
    tibialis = LEGS.index("tibialis-raise")
    answer = guided.keep(plan, found, 2, 1, [], [guided.Done(tibialis, 1, 20)])
    assert answer == "Tibialis raise has no set 1"


def test_a_stale_revision_is_refused_and_changes_nothing(plan: Session) -> None:
    """The first choice starts the day's progress (revision 1) and changes it (2)."""
    assert guided.choose_length(plan, _today(plan), 0, 30, ()) == 2
    assert guided.choose_length(plan, _today(plan), 0, 20, ()) == guided.STALE
    assert guided.choose_length(plan, _today(plan), 1, 20, ()) == guided.STALE
    assert guided.choose_length(plan, _today(plan), 2, 20, ()) == 3
    length = _today(plan).length
    assert length is not None
    assert length.minutes == 20


def test_as_planned_again_undoes_a_shorter_day(plan: Session) -> None:
    _choose(plan, 20)
    found = _choose(plan, None)
    assert found.length is not None
    assert found.length.minutes is None
    assert tuple(_sets(found).values()) == (3, 3, 3, 4, 3, 3, 3, 3)


def test_a_keep_for_another_exercise_or_odd_minutes_is_refused(plan: Session) -> None:
    found = _today(plan)
    assert guided.choose_length(plan, found, 0, 20, ("pull-up",)) == guided.NOT_IN_SESSION
    assert (
        guided.choose_length(plan, found, 0, 25, ()) == "choose 40, 30, 20 minutes, or as planned"
    )
    assert guided.kept(plan, DAY) is None


def test_a_saved_session_cannot_change_its_length(plan: Session) -> None:
    found = _choose(plan, 30)
    guided.keep(plan, found, 2, 1, [], [guided.Done(0, 1, 6)])
    assert isinstance(guided.save(plan, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.choose_length(plan, found, 3, 20, ()) == guided.SAVED


def test_a_shorter_day_saves_its_minutes_and_what_it_planned(plan: Session) -> None:
    found = _choose(plan, 20)
    done = [guided.Done(0, 1, 6), guided.Done(0, 2, 6)]
    guided.keep(plan, found, 2, 2, [], done)
    saved = guided.save(plan, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = plan.get_one(Workout, saved.workout_id)
    assert workout.minutes == 20
    sets = (2, 0, 2, 0, 2, 0, 0, 0)
    assert workout.planned == {slug: {"sets": n} for slug, n in zip(LEGS, sets, strict=True)}


@pytest.mark.parametrize(
    ("slug", "timed", "chosen", "saved"),
    [
        ("hiit", None, 20, None),  # one short item, no warm-up: nothing to cut
        ("zone2", None, 40, 40),  # its 45 minutes shorten to 40
        ("legs", None, 40, 40),  # third sets go
        ("legs", 26, 40, None),  # someone this quick fits 40 as planned, warm-up and all
        ("legs", 26, 30, 30),  # the same sets, but ramp sets replace the warm-up
    ],
)
def test_a_length_that_changed_nothing_saves_as_planned(
    plan: Session, slug: str, timed: int | None, chosen: int, saved: int | None
) -> None:
    """Minutes chosen that cut no set, shortened nothing, dropped nothing and kept the warm-up
    save no minutes: the day still counts toward "usually" and as done as planned."""
    if timed is not None:
        _timed_legs(plan, minutes=timed, times=3)
    _at(plan, slug)
    found = _choose(plan, chosen)
    guided.keep(plan, found, 2, 1, [], [guided.Done(0, 1, 8)])
    result = guided.save(plan, DAY, DAY, BERLIN)
    assert isinstance(result, workout_log.Saved)
    assert plan.get_one(Workout, result.workout_id).minutes == saved


def test_a_shortened_cardio_is_saved_as_dropped_not_missed(plan: Session) -> None:
    _at(plan, "moderate-cardio")
    found = _choose(plan, 30)
    guided.keep(plan, found, 2, 1, [], [guided.Done(0, 1, 10)])
    saved = guided.save(plan, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = plan.get_one(Workout, saved.workout_id)
    assert workout.planned is not None
    assert workout.planned["moderate-cardio"] == {"sets": 0}
    assert workout.planned["ab-rollout"] == {"sets": 2}


# ---------------------------------------------------------------- pace (ADR-0082)


def _timed_legs(
    session: Session,
    minutes: int,
    times: int,
    place: Place = Place.HOME,
    day_minutes: int | None = None,
) -> None:
    """``times`` Legs workouts before DAY whose sets took ``minutes`` in all: one-minute sets
    every five minutes, so no gap is a break (``minutes`` is one more than a multiple of 5)."""
    legs = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == "legs")).one()
    jump = session.scalars(select(Exercise).where(Exercise.slug == "jump-squat")).one()
    for n in range(times):
        start = datetime(2026, 10, 1 + n, 16, 0, tzinfo=UTC)
        workout = Workout(
            local_date=date(2026, 10, 1 + n),
            template_id=legs.id,
            status=WorkoutStatus.DONE,
            place=place,
            minutes=day_minutes,
        )
        workout.sets = [
            SetLog(
                exercise_id=jump.id,
                ladder_step_id=jump.ladder[0].id,
                set_no=set_no,
                side=Side.BOTH,
                value=6,
                started_at=at,
                done_at=at + timedelta(minutes=1),
            )
            for set_no, at in (
                (k + 1, start + timedelta(minutes=5 * k)) for k in range((minutes - 1) // 5 + 1)
            )
        ]
        session.add(workout)
    session.flush()


def test_three_timed_sessions_as_planned_set_the_pace(plan: Session) -> None:
    """Legs as planned is about 44 minutes of work: done in 66, the person's pace is 1.5."""
    _timed_legs(plan, minutes=66, times=3)
    found = _today(plan)
    assert found.length is not None
    assert found.length.pace == pytest.approx(66 / 44, rel=0.05)
    assert found.minutes == found.length.planned  # the paced estimate, warm-up included
    assert found.length.planned == pytest.approx(66 + 5, abs=1)
    slower = _choose(plan, 40)
    assert sum(_sets(slower).values()) < 16  # at that pace two sets each don't fit


@pytest.mark.parametrize(
    ("times", "place", "day_minutes"),
    [(2, Place.HOME, None), (3, Place.GYM, None), (3, Place.HOME, 30)],
)
def test_the_pace_needs_three_timed_sessions_at_the_place_done_as_planned(
    plan: Session, times: int, place: Place, day_minutes: int | None
) -> None:
    _timed_legs(plan, minutes=66, times=times, place=place, day_minutes=day_minutes)
    length = _today(plan).length
    assert length is not None
    assert length.pace == 1.0
