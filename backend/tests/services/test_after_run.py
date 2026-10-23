"""The block after a conditioning session's cardio (ADR-0066): once the cardio is logged,
however it was logged, the rest of the session stays open that day and joins its workout."""

from datetime import date, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    SessionProgress,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.services import cardio, guided, home, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import position

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
# A cardio day with a paired block after the run. The bundled plan's own cardio day may or may
# not have one, so the test plan replaces that session whole.
CARDIO_CORE = """[[sessions]]
slug = "moderate-cardio"
type = "conditioning"
name = "Cardio + core"
focus = "~35 min at 75-80% effort, then core"
items = [
  { exercise = "moderate-cardio", sets = 1, rep_min = 30, rep_max = 40 },
  { exercise = "hanging-raise", sets = 2, rep_min = 8, rep_max = 15, pair = 1 },
  { exercise = "back-extension", sets = 2, rep_min = 10, rep_max = 15, pair = 1 },
]

"""


def _seeded(session: Session) -> Session:
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    start = text.index('[[sessions]]\nslug = "moderate-cardio"')
    end = text.index("[[sessions]]", start + 1)
    text = text[:start] + CARDIO_CORE + text[end:]
    apply_seed(session, load_plan(text))
    session.flush()
    return session


def _queue_at(session: Session, slug: str) -> SessionTemplate:
    template = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id = template.id
    session.flush()
    return template


def _run_logged(session: Session, token: str = "a" * 32) -> int:
    """The run counted as a band workout or the web's Log activity would count it."""
    logged = cardio.log(session, DAY, BERLIN, "moderate-cardio", 35, None, token)
    assert isinstance(logged, cardio.Logged)
    return logged.saved.workout_id


def _after(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    assert plan.after_run
    return plan


def _slugs(session: Session, workout_id: int) -> list[str]:
    rows = session.scalars(
        select(Exercise.slug).join(SetLog).where(SetLog.workout_id == workout_id)
    )
    return sorted(set(rows))


def test_the_block_after_a_logged_run_stays_open(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    _run_logged(seeded)
    assert workout_log.target(seeded, DAY, BERLIN) is None  # the day's session is done
    plan = _after(seeded)  # before ADR-0066: nothing left today
    assert [i.slug for i in plan.items] == ["hanging-raise", "back-extension"]
    assert (plan.name, plan.warm_up) == ("Cardio + core", False)
    assert len(plan.order) == 4  # two pairs' rounds, alternating


def test_the_block_joins_the_runs_workout_and_the_queue_moves_once(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    run = _run_logged(seeded)
    moved = position(seeded)
    assert moved is not None
    plan = _after(seeded)
    sets = [guided.Done(o.item, o.set_no, 10) for o in plan.order]
    assert guided.keep(seeded, plan, 0, len(sets), [], sets) == 1
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert saved == workout_log.Saved(run, already_saved=False)
    assert _slugs(seeded, run) == ["back-extension", "hanging-raise", "moderate-cardio"]
    workouts = seeded.scalars(select(Workout).where(Workout.local_date == DAY)).all()
    assert [w.id for w in workouts] == [run]  # no second workout, so nothing clashes
    after = position(seeded)
    assert after is not None
    assert after.pointer == moved.pointer  # moved by the run, not again by the block
    assert guided.save(seeded, DAY, DAY, BERLIN) == workout_log.Saved(run, already_saved=True)
    assert guided.today(seeded, DAY, BERLIN) is None  # all done


def test_a_typed_run_leaves_the_block_open_too(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    draft = workout_log.draft(seeded, "run 35 min", DAY, BERLIN)  # Telegram or the web's log
    assert isinstance(workout_log.save(seeded, draft, BERLIN), workout_log.Saved)
    assert [i.slug for i in _after(seeded).items] == ["hanging-raise", "back-extension"]


def test_a_guided_run_saved_alone_gives_way_to_the_block(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    whole = guided.today(seeded, DAY, BERLIN)
    assert whole is not None
    assert not whole.after_run
    assert guided.keep(seeded, whole, 0, 1, [], [guided.Done(0, 1, 35)]) == 1
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    plan = _after(seeded)
    assert guided.keep(seeded, plan, 1, 0, [], []) == guided.STALE  # a page from before
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)]) == 1  # afresh
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.after_run, kept.saved, kept.sets) == (True, False, (guided.Done(0, 1, 9),))
    again = guided.save(seeded, DAY, DAY, BERLIN)
    assert again == workout_log.Saved(saved.workout_id, already_saved=False)
    assert _slugs(seeded, saved.workout_id) == ["hanging-raise", "moderate-cardio"]
    left = _after(seeded)  # only back extensions are left
    assert [i.slug for i in left.items] == ["back-extension"]


def test_the_block_is_not_saved_once_its_day_is_over(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    _run_logged(seeded)
    plan = _after(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 10)])
    later = DAY + timedelta(days=1)
    assert isinstance(guided.save(seeded, DAY, later, BERLIN), workout_log.Stale)
    assert guided.pending(seeded, later) == []  # its day's session is logged: not offered


def test_progress_for_the_block_is_dropped_when_the_run_is_undone(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    run = _run_logged(seeded)
    guided.keep(seeded, _after(seeded), 0, 1, [], [guided.Done(0, 1, 10)])
    seeded.delete(seeded.get_one(Workout, run))  # as an undo would
    seeded.flush()
    whole = guided.today(seeded, DAY, BERLIN)
    assert whole is not None
    assert not whole.after_run
    assert guided.keep(seeded, whole, 0, 0, [], []) == 1  # the whole session, afresh
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.after_run, kept.sets) == (False, ())


def test_a_cardio_only_day_is_done_once_its_cardio_is(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "zone2")  # Long zone 2: the walk and nothing after it
    logged = cardio.log(seeded, DAY, BERLIN, "zone2", 60, None, "a" * 32)
    assert isinstance(logged, cardio.Logged)
    assert logged.planned
    assert guided.today(seeded, DAY, BERLIN) is None


def test_a_strength_day_done_offers_nothing_after(session: Session) -> None:
    seeded = _seeded(session)
    plan = guided.today(seeded, DAY, BERLIN)  # Legs, at the start of the queue
    assert plan is not None
    assert plan.kind == "strength"
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)])
    assert isinstance(guided.save(seeded, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.today(seeded, DAY, BERLIN) is None


def test_home_names_the_block_after_the_run(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    _run_logged(seeded)
    found = home.home(seeded, DAY, BERLIN)
    assert found.today == "Cardio + core, after your run"
    assert found.today_usual_minutes is None  # the whole session's usual time would mislead


def test_the_run_is_the_days_planned_cardio(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    found = cardio.planned(seeded, DAY, BERLIN)  # before ADR-0066: none, so a run was an extra
    assert found is not None
    assert (found.kind, found.session) == ("moderate-cardio", "Cardio + core")
    logged = cardio.log(seeded, DAY, BERLIN, "moderate-cardio", 35, None, "a" * 32)
    assert isinstance(logged, cardio.Logged)
    assert logged.planned  # it completed the day's session
    assert cardio.planned(seeded, DAY, BERLIN) is None


def test_a_strength_session_is_never_planned_cardio(session: Session) -> None:
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    start = text.index('[[sessions]]\nslug = "moderate-cardio"')
    end = text.index("[[sessions]]", start + 1)
    strength = CARDIO_CORE.replace('type = "conditioning"', 'type = "strength"')
    apply_seed(session, load_plan(text[:start] + strength + text[end:]))
    session.flush()
    _queue_at(session, "moderate-cardio")
    assert cardio.planned(session, DAY, BERLIN) is None


def test_the_bundled_cardio_day_opens_its_block_after_the_run(session: Session) -> None:
    apply_seed(session, load_plan())
    session.flush()
    day = _queue_at(session, "moderate-cardio")
    _run_logged(session)
    plan = _after(session)
    assert plan.name == day.name
    assert plan.items
    assert all(i.slug != "moderate-cardio" for i in plan.items)


def _block_saved(session: Session) -> int:
    _queue_at(session, "moderate-cardio")
    run = _run_logged(session)
    plan = _after(session)
    sets = [guided.Done(o.item, o.set_no, 10) for o in plan.order]
    guided.keep(session, plan, 0, len(sets), [], sets)
    assert guided.save(session, DAY, DAY, BERLIN) == workout_log.Saved(run, already_saved=False)
    return run


def _as_if_unsaved(session: Session) -> None:
    """A second save that read the progress before the first one committed."""
    row = session.scalars(select(SessionProgress).where(SessionProgress.local_date == DAY)).one()
    row.saved_workout_id = None
    session.flush()


def test_a_repeated_save_of_the_block_adds_nothing(session: Session) -> None:
    seeded = _seeded(session)
    run = _block_saved(seeded)
    count = len(seeded.get_one(Workout, run).sets)
    _as_if_unsaved(seeded)
    assert guided.save(seeded, DAY, DAY, BERLIN) == workout_log.Saved(run, already_saved=True)
    assert len(seeded.get_one(Workout, run).sets) == count


def test_a_racing_save_of_the_block_is_rolled_back(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded = _seeded(session)
    run = _block_saved(seeded)
    count = len(seeded.get_one(Workout, run).sets)
    _as_if_unsaved(seeded)
    block = ("hanging-raise", "back-extension")  # its view: none of the block is in yet
    monkeypatch.setattr(
        guided, "_left", lambda _s, _w, items: tuple(i for i in items if i.slug in block)
    )
    assert guided.save(seeded, DAY, DAY, BERLIN) == workout_log.Saved(run, already_saved=True)
    assert len(seeded.get_one(Workout, run).sets) == count
    added = seeded.scalars(select(Event).where(Event.kind == "workout.added")).all()
    assert len(added) == 1


def test_a_conditioning_day_without_a_run_offers_nothing_after(session: Session) -> None:
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    start = text.index('[[sessions]]\nslug = "moderate-cardio"')
    end = text.index("[[sessions]]", start + 1)
    no_run = CARDIO_CORE.replace(
        '  { exercise = "moderate-cardio", sets = 1, rep_min = 30, rep_max = 40 },\n', ""
    )
    apply_seed(session, load_plan(text[:start] + no_run + text[end:]))
    session.flush()
    _queue_at(session, "moderate-cardio")
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    guided.keep(session, plan, 0, 1, [], [guided.Done(0, 1, 10)])
    assert isinstance(guided.save(session, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.today(session, DAY, BERLIN) is None  # nothing left today, not "after your run"


def test_a_session_saved_without_its_run_offers_nothing_after(session: Session) -> None:
    seeded = _seeded(session)
    _queue_at(seeded, "moderate-cardio")
    whole = guided.today(seeded, DAY, BERLIN)
    assert whole is not None
    raise_set = next(o for o in whole.order if whole.items[o.item].slug == "hanging-raise")
    guided.keep(seeded, whole, 0, 1, [], [guided.Done(raise_set.item, 1, 10)])
    assert isinstance(guided.save(seeded, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.today(seeded, DAY, BERLIN) is None
