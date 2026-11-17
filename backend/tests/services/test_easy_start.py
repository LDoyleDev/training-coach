"""The easy start's store (ADR-0094): the switch and its day, the workouts that count (a person's
own done strength or conditioning sessions, nobody else's), each step up told once, and the two
offers. Never for the owner, and not once it is over."""

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, PlanNotice, SessionTemplate, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.easy_start import Phase, Setting, State
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import easy_start, users
from training_coach.services.seed import apply_seed, load_plan

MEMBER = 2
KINDS = ("strength", "conditioning", "recovery")
START = date(2026, 12, 1)


def day(n: int) -> date:
    return START + timedelta(days=n)


@pytest.fixture
def people(engine: Engine) -> Engine:
    """The owner and a member, each with the bundled plan."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=MEMBER, role=users.MEMBER))
        shared.flush()
        apply_seed(shared, load_plan())
    return engine


@pytest.fixture
def member(people: Engine) -> Iterator[Session]:
    with make_session_factory(people, user_id=MEMBER)() as theirs:
        yield theirs


def _log(
    session: Session, on: date, kind: str = "strength", status: str = WorkoutStatus.DONE
) -> None:
    """A workout of the person's first session of ``kind`` (one is made if they have none)."""
    template = session.scalars(
        select(SessionTemplate).where(SessionTemplate.kind == kind).order_by(SessionTemplate.id)
    ).first()
    if template is None:
        template = SessionTemplate(
            position=90 + KINDS.index(kind), slug=kind, name=kind, focus=kind, kind=kind
        )
        session.add(template)
        session.flush()
    session.add(Workout(local_date=on, template_id=template.id, status=status))
    session.flush()


def _sessions(session: Session, *days: int) -> None:
    for n in days:
        _log(session, day(n))


def test_off_with_no_row_and_on_from_the_first_day_it_is_turned_on(member: Session) -> None:
    assert easy_start.setting(member) == Setting(False)
    assert easy_start.turn(member, True, day(0)) is None
    assert easy_start.setting(member) == Setting(True, day(0))
    assert easy_start.current(member, day(0)).phase is Phase.WAITING
    assert member.scalars(select(Event.payload)).all()[-1] == {"easy_start": True}


def test_off_and_on_again_keeps_its_first_day(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    assert easy_start.turn(member, False, day(3)) is None
    assert easy_start.current(member, day(3)).phase is Phase.OFF
    assert easy_start.turn(member, True, day(5)) is None
    assert easy_start.setting(member).since == day(0)


def test_a_repeated_press_changes_nothing(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    before = len(member.scalars(select(Event)).all())
    assert easy_start.turn(member, True, day(2)) is None
    assert len(member.scalars(select(Event)).all()) == before


def test_only_done_strength_and_conditioning_sessions_count(member: Session) -> None:
    _log(member, day(0))
    _log(member, day(1), "conditioning")
    _log(member, day(2), "recovery")
    _log(member, day(3), status=WorkoutStatus.REST)
    _log(member, day(4), status=WorkoutStatus.SKIPPED)
    member.add(Workout(local_date=day(5), status=WorkoutStatus.DONE, activity="walk"))  # extra
    member.flush()
    assert sorted(easy_start.counted(member)) == [day(0), day(1)]


def test_another_persons_workouts_never_count(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=users.OWNER)) as mine:
        for n in range(6):
            _log(mine, day(n))
    with session_scope(make_session_factory(people, user_id=MEMBER)) as theirs:
        assert easy_start.counted(theirs) == []
        easy_start.turn(theirs, True, day(0))
        assert easy_start.current(theirs, day(20)).phase is Phase.WAITING


def test_the_light_start_counts_from_the_first_workout_after_it_went_on(member: Session) -> None:
    _log(member, day(-3))  # before the switch: doesn't count
    easy_start.turn(member, True, day(0))
    _sessions(member, 1, 3)
    found = easy_start.current(member, day(4))
    assert (found.phase, found.count, found.of, found.until) == (Phase.LIGHT, 2, 4, day(15))


def _to_lower(session: Session) -> None:
    """On from day 0, four sessions in the first week: one set lower from day 14."""
    easy_start.turn(session, True, day(0))
    _sessions(session, 0, 2, 4, 6)


def test_one_set_lower_is_told_once(member: Session) -> None:
    _to_lower(member)
    assert easy_start.tell_due(member, day(13)) is None
    assert easy_start.tell_due(member, day(14)) is Phase.LOWER
    assert easy_start.tell_due(member, day(15)) is None
    (notice,) = member.scalars(select(PlanNotice)).all()
    assert notice.text == easy_start.TOLD[Phase.LOWER]
    assert notice.text.startswith("Your light start is done: from today, one set fewer")


def test_after_one_more_easy_week_one_set_lower_isnt_told_again(member: Session) -> None:
    """Each step up is written once (ADR-0094 Stored): back to one set lower after the extra
    week, the notice already written stands."""
    _to_lower(member)
    assert easy_start.tell_due(member, day(14)) is Phase.LOWER
    assert easy_start.extend(member, day(14)) is None  # the light start until day 21
    assert easy_start.current(member, day(21)).phase is Phase.LOWER
    assert easy_start.tell_due(member, day(21)) is None
    assert len(member.scalars(select(PlanNotice)).all()) == 1


def test_the_end_is_told_once_with_the_walks_and_account(member: Session) -> None:
    _to_lower(member)
    _sessions(member, *range(14, 30, 2))  # 8 sessions in one set lower
    assert easy_start.tell_due(member, day(20)) is Phase.LOWER
    assert easy_start.tell_due(member, day(41)) is None
    assert easy_start.tell_due(member, day(42)) is Phase.DONE  # 28 days after day 14
    assert easy_start.tell_due(member, day(50)) is None
    texts = member.scalars(select(PlanNotice.text).order_by(PlanNotice.id)).all()
    assert texts == [easy_start.TOLD[Phase.LOWER], easy_start.TOLD[Phase.DONE]]
    assert "15-30 minutes" in texts[1]
    assert "on Account" in texts[1]
    assert all(len(t) <= 300 for t in texts)  # the notice's column


def test_nothing_is_told_while_it_is_off(member: Session) -> None:
    _to_lower(member)
    easy_start.turn(member, False, day(10))
    assert easy_start.tell_due(member, day(20)) is None
    assert member.scalars(select(PlanNotice)).all() == []


def test_the_owner_is_refused(people: Engine) -> None:
    with session_scope(make_session_factory(people, user_id=users.OWNER)) as mine:
        assert easy_start.turn(mine, True, day(0)) == easy_start.OWNER
        assert easy_start.setting(mine) == Setting(False)
        assert not easy_start.changeable(mine, day(0))
        assert easy_start.turn(mine, False, day(0)) is None  # already off: nothing to refuse


def test_once_over_it_cant_be_turned_off(member: Session) -> None:
    _to_lower(member)
    _sessions(member, *range(14, 30, 2))
    assert easy_start.changeable(member, day(41))
    assert not easy_start.changeable(member, day(42))
    assert easy_start.turn(member, False, day(42)) == easy_start.OVER
    assert easy_start.setting(member).on


def test_off_and_over_since_it_cant_be_turned_on_again(member: Session) -> None:
    _to_lower(member)
    _sessions(member, *range(14, 30, 2))
    assert easy_start.turn(member, False, day(30)) is None  # off before the end
    assert easy_start.changeable(member, day(41))
    assert easy_start.turn(member, True, day(50)) == easy_start.OVER  # its first day is kept
    assert not easy_start.setting(member).on


def test_months_of_workouts_before_it_was_ever_on_dont_make_it_over(member: Session) -> None:
    _sessions(member, *range(0, 60, 2))
    assert easy_start.changeable(member, day(60))
    assert easy_start.turn(member, True, day(60)) is None
    assert easy_start.current(member, day(60)).phase is Phase.WAITING


def test_one_more_easy_week_brings_the_light_start_back(member: Session) -> None:
    _to_lower(member)
    assert easy_start.extend(member, day(13)) == easy_start.NO_WEEK  # still in the light start
    assert easy_start.extend(member, day(15)) is None
    assert easy_start.setting(member).weeks_light == 1
    assert easy_start.current(member, day(15)).phase is Phase.LIGHT  # until day 21
    assert easy_start.current(member, day(21)).phase is Phase.LOWER


def test_at_most_two_easy_weeks(member: Session) -> None:
    _to_lower(member)
    assert easy_start.extend(member, day(15)) is None
    assert easy_start.extend(member, day(21)) is None
    assert easy_start.extend(member, day(28)) == easy_start.NO_WEEK
    found = easy_start.setting(member)
    assert (found.weeks_light, found.weeks_lower) == (2, 0)


def test_a_restart_after_a_gap_counts_again_from_today(member: Session) -> None:
    _to_lower(member)
    easy_start.tell_due(member, day(14))
    easy_start.extend(member, day(15))
    assert easy_start.restart(member, day(10)) == easy_start.NO_RESTART  # no gap yet
    assert easy_start.restart(member, day(30)) is None  # 24 days since day 6
    assert easy_start.setting(member) == Setting(True, day(30))
    row = users.settings_row(member)
    assert row is not None
    assert row.easy_start_told is None
    assert easy_start.current(member, day(30)).phase is Phase.WAITING
    kinds = member.scalars(select(Event.kind).where(Event.kind.like("easy_start.%"))).all()
    assert kinds == ["easy_start.extended", "easy_start.restarted"]


WALK = " Then a 5-10 minute walk, if you can walk safely on your own."
DEC_3, DEC_31 = date(2026, 12, 3), date(2026, 12, 31)


@pytest.mark.parametrize(
    ("found", "line"),
    [
        (State(Phase.OFF), None),
        (
            State(Phase.WAITING),
            "Easy start: light, session 1 of 4. One set of each, at the bottom of its range."
            + WALK,
        ),
        (
            State(Phase.LIGHT, count=1, of=4, until=DEC_3),
            "Easy start: light, session 2 of 4 (until at least 3 Dec)." + WALK,
        ),
        (
            State(Phase.LIGHT, count=4, of=4, until=DEC_3, ending=True),
            "Easy start: light (until at least 3 Dec). Next: one set fewer than planned of each."
            + WALK,
        ),
        (
            State(Phase.LOWER, count=0, of=8, until=DEC_31, fresh=True),
            "New today: Easy start: one set fewer of each, session 1 of 8 (until at least 31 Dec)."
            + WALK,
        ),
        (
            State(Phase.LOWER, count=7, of=8, until=DEC_31, ending=True),
            "Easy start: one set fewer of each, session 8 of 8 (until at least 31 Dec). Next: full"
            " sessions." + WALK,
        ),
        (
            State(Phase.LOWER, count=9, of=8, until=DEC_31),
            "Easy start: one set fewer of each (until at least 31 Dec)." + WALK,
        ),
        (State(Phase.DONE, fresh=True), "Full sessions from today: your easy start is done."),
        (State(Phase.DONE), None),
    ],
)
def test_the_overviews_line(found: State, line: str | None) -> None:
    assert easy_start.line(found) == line
