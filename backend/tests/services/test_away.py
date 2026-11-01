"""Away, no equipment (ADR-0086): a third place on Today's switch, for the day only, with each
exercise at the highest step at or below the person's level that needs no kit."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from tests import factories
from training_coach.db.models import Exercise, LadderStep, SessionTemplate, Workout
from training_coach.domain.enums import Place, Places
from training_coach.services import (
    blocks,
    guided,
    session_levels,
    today,
    user_settings,
    users,
    workout_log,
)
from training_coach.services.seed import ItemSeed, apply_seed

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 11, 2)


def _seeded(session: Session) -> Session:
    apply_seed(session, factories.plan_with_away())
    session.flush()
    return session


def _at(session: Session, slug: str, step: str) -> int:
    """Put the person at ``step`` of ``slug``'s ladder; its id."""
    exercise = session.scalars(select(Exercise).where(Exercise.slug == slug)).one()
    found = next(s for s in exercise.ladder if s.name == step)
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    state.ladder_step_id = found.id
    session.flush()
    return found.id


def _level(session: Session, slug: str) -> int:
    exercise = session.scalars(select(Exercise).where(Exercise.slug == slug)).one()
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    return state.ladder_step_id


def _away(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    assert guided.switch(session, plan, Place.AWAY, confirm=False) is None
    away = guided.today(session, DAY, BERLIN)
    assert away is not None
    return away


def _item(plan: guided.Guided | today.SessionPlan, slug: str) -> today.ItemPlan:
    return next(i for i in plan.items if i.slug == slug)


def test_away_is_offered_with_an_away_version_also_to_someone_at_home_only(
    session: Session,
) -> None:
    seeded = _seeded(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert (plan.place, plan.places, plan.switch) == (Place.HOME, (Place.HOME, Place.AWAY), True)
    user_settings.update(seeded, places=Places.BOTH)
    both = guided.today(seeded, DAY, BERLIN)
    assert both is not None
    assert both.places == (Place.HOME, Place.GYM, Place.AWAY)


def test_a_session_without_an_away_version_offers_no_away(session: Session) -> None:
    seeded = _seeded(session)
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = seeded.scalars(
        select(SessionTemplate.id).where(SessionTemplate.slug == "recovery")
    ).one()
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert (plan.places, plan.switch) == ((Place.HOME,), False)


def test_away_is_the_days_only_and_never_the_place_today_starts_at(session: Session) -> None:
    seeded = _seeded(session)
    user_settings.update(seeded, places=Places.BOTH, place=Place.GYM)
    away = _away(seeded)
    assert away.place is Place.AWAY
    assert [i.slug for i in away.items] == [i.exercise for i in factories.AWAY_LEGS]
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.place, kept.sets) == (Place.AWAY, ())
    prefs = user_settings.load(seeded)
    assert (prefs.places, prefs.place) == (Places.BOTH, Place.GYM)  # untouched
    tomorrow = guided.today(seeded, DAY + timedelta(days=1), BERLIN)
    assert tomorrow is not None
    assert tomorrow.place is Place.GYM  # starts where it would have


def test_every_reader_of_the_day_sees_the_away_version(session: Session) -> None:
    seeded = _seeded(session)
    _away(seeded)
    found = today.today(seeded, DAY, BERLIN)
    assert found is not None
    assert found.session.place is Place.AWAY  # the bot's /today
    assert today.away_on(seeded, DAY)
    assert not today.away_on(seeded, DAY + timedelta(days=1))


def test_switching_back_drops_the_away_day_and_asks_first_with_sets_kept(
    session: Session,
) -> None:
    seeded = _seeded(session)
    away = _away(seeded)
    assert guided.keep(seeded, away, 1, 1, [], [guided.Done(0, 1, 6)]) == 2
    assert guided.switch(seeded, away, Place.HOME, confirm=False) == 1
    assert guided.kept(seeded, DAY) is not None  # nothing changed yet
    assert guided.switch(seeded, away, Place.HOME, confirm=True) is None
    assert guided.kept(seeded, DAY) is None
    home = guided.today(seeded, DAY, BERLIN)
    assert home is not None
    assert home.place is Place.HOME


def test_a_step_that_needs_kit_gives_way_to_the_highest_one_below_that_needs_none(
    session: Session,
) -> None:
    seeded = _seeded(session)
    goblet = _at(seeded, "bulgarian-split-squat", "Goblet hold, 16 kg")
    _at(seeded, "jump-squat", "Holding 8 kg")
    _at(seeded, "tibialis-raise", "Single leg")
    away = _away(seeded)
    split = _item(away, "bulgarian-split-squat")
    assert (split.step, split.no_kit) == ("Bodyweight, back foot on chair", True)
    jump = _item(away, "jump-squat")
    assert (jump.step, jump.no_kit) == ("Pause at bottom, then jump", True)
    tibialis = _item(away, "tibialis-raise")
    assert (tibialis.step, tibialis.no_kit) == ("Single leg", False)  # needs no kit: the level
    assert _level(seeded, "bulgarian-split-squat") == goblet  # the level never moves


def test_at_home_the_same_levels_train_as_they_are(session: Session) -> None:
    seeded = _seeded(session)
    _at(seeded, "bulgarian-split-squat", "Goblet hold, 16 kg")
    home = guided.today(seeded, DAY, BERLIN)
    assert home is not None
    split = _item(home, "bulgarian-split-squat")
    assert (split.step, split.no_kit) == ("Goblet hold, 16 kg", False)


def test_a_strength_block_checks_the_step_a_strength_session_would_train(
    session: Session,
) -> None:
    """One step up from Bodyweight is Goblet hold, 8 kg (ADR-0028): away, it gives way again."""
    seeded = _seeded(session)
    _at(seeded, "bulgarian-split-squat", "Bodyweight, back foot on chair")
    exercise = seeded.scalars(
        select(Exercise).where(Exercise.slug == "bulgarian-split-squat")
    ).one()
    harder, _ = blocks.step_for(seeded, exercise, strength=True)
    assert harder.name == "Goblet hold, 8 kg"
    assert blocks.kit_free(seeded, exercise, harder).name == "Bodyweight, back foot on chair"


def test_the_sets_are_saved_away_at_the_step_done_and_the_level_stays(session: Session) -> None:
    seeded = _seeded(session)
    goblet = _at(seeded, "bulgarian-split-squat", "Goblet hold, 8 kg")
    away = _away(seeded)
    index = next(n for n, i in enumerate(away.items) if i.slug == "bulgarian-split-squat")
    assert guided.keep(seeded, away, 1, 1, [], [guided.Done(index, 1, 10, 10)]) == 2
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = seeded.get_one(Workout, saved.workout_id)
    assert workout.place == "away"
    (done,) = workout.sets[:1]
    assert seeded.get_one(LadderStep, done.ladder_step_id).name == "Bodyweight, back foot on chair"
    assert _level(seeded, "bulgarian-split-squat") == goblet


def test_a_typed_log_on_an_away_day_is_filed_away_at_a_step_that_needs_no_kit(
    session: Session,
) -> None:
    seeded = _seeded(session)
    _at(seeded, "bulgarian-split-squat", "Goblet hold, 8 kg")
    _away(seeded)
    draft = workout_log.draft(seeded, "bulgarian split squat 10 10 10", DAY, BERLIN)
    assert draft.problems == ()
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = seeded.get_one(Workout, saved.workout_id)
    assert workout.place == "away"
    steps = {seeded.get_one(LadderStep, s.ladder_step_id).name for s in workout.sets}
    assert steps == {"Bodyweight, back foot on chair"}


def test_a_level_picked_for_today_away_is_done_as_picked_and_kit_shows_locked(
    session: Session,
) -> None:
    """ADR-0080 still works away: the person decides; the picker says what each step needs."""
    seeded = _seeded(session)
    away = _away(seeded)
    split = seeded.scalars(select(Exercise).where(Exercise.slug == "bulgarian-split-squat")).one()
    goblet = next(s for s in split.ladder if s.name == "Goblet hold, 8 kg")
    changed = session_levels.change(
        seeded, away, 1, "bulgarian-split-squat", goblet.id, session_levels.Scope.TODAY
    )
    assert isinstance(changed, session_levels.Changed)
    assert changed.warning == "Goblet hold, 8 kg needs an 8 kg kettlebell, not in your kit."
    picked = guided.today(seeded, DAY, BERLIN)
    assert picked is not None
    item = _item(picked, "bulgarian-split-squat")
    assert (item.step, item.no_kit) == ("Goblet hold, 8 kg", False)
    ladder = session_levels.ladders(seeded, ["bulgarian-split-squat"], away=True)
    rungs = {r.name: r.missing for r in ladder["bulgarian-split-squat"]}
    assert rungs["Bodyweight, back foot on chair"] == ()
    assert rungs["Goblet hold, 8 kg"] == ("an 8 kg kettlebell",)


def test_short_on_time_trims_the_away_version_as_any_day(session: Session) -> None:
    minutes = 20
    seeded = _seeded(session)
    away = _away(seeded)
    assert away.length is not None
    assert away.length.planned > minutes
    assert away.length is not None
    revision = guided.kept(seeded, DAY)
    assert revision is not None
    assert isinstance(guided.choose_length(seeded, away, revision.revision, minutes, []), int)
    short = guided.today(seeded, DAY, BERLIN)
    assert short is not None
    assert short.place is Place.AWAY
    assert short.length is not None
    assert short.length.minutes == minutes
    assert short.minutes <= minutes < away.minutes  # ramp sets in place of the warm-up


def test_away_also_passes_over_a_step_the_person_avoids(session: Session) -> None:
    """ADR-0083's preferences lock steps away too: "Keep me off the floor" at a full plank
    trains the highest step below it that needs no kit and no floor."""
    plank = (ItemSeed(exercise="plank", sets=2, rep_min=10, rep_max=30),)
    apply_seed(session, factories.plan_with_away(items=plank))
    session.flush()
    _at(session, "plank", "Full plank")
    user_settings.update(session, avoid_floor=True)
    away = _away(session)
    item = _item(away, "plank")
    assert (item.step, item.no_kit) == ("Hands on a chair seat against a wall", True)
