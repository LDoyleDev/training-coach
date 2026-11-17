"""The easy start (ADR-0094): the person's switch and where it stands, from their settings row
and their counted workouts, with each step up told once as a plan notice (ADR-0087). The rules
are in ``domain.easy_start``; callers pass a session bound to the person (ADR-0029)."""

from dataclasses import replace
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, PlanNotice, SessionTemplate, UserSettings, Workout
from training_coach.db.session import bound_user
from training_coach.domain import easy_start as domain
from training_coach.domain.easy_start import Phase, Setting, State
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import users

COUNTED = ("strength", "conditioning")  # recovery sessions don't count (or change)
TOLD = {
    Phase.LOWER: "Your light start is done: from today, one set fewer than planned of each"
    " exercise.",
    Phase.DONE: "Your easy start is done: full sessions from today. Build your walks up to 15-30"
    " minutes. Minutes, exercises per session and days are on Account.",
}
OWNER = "The easy start isn't for the owner's plan."
OVER = "Your easy start is over, so it can't be changed."
NO_WEEK = "One more easy week isn't on offer now."
NO_RESTART = "Starting the easy start again is offered after 14 days without a workout."
WALK = " Then a 5-10 minute walk, if you can walk safely on your own."  # Decided 12
FULL = "Full sessions from today: your easy start is done."


def _on(day: date) -> str:
    """A date as the line says it: "3 Dec"."""
    return f"{day.day} {day:%b}"


def line(found: State) -> str | None:
    """The overview's line for the easy start (ADR-0094), as the web and the bot show it: the
    phase, its session and the day it runs until at least, what comes next near its end, and the
    walk. None when there is nothing to say: off, or done before today."""
    until = f" (until at least {_on(found.until)})" if found.until is not None else ""
    if found.phase is Phase.WAITING:
        text = (
            f"Easy start: light, session 1 of {domain.LIGHT_SESSIONS}. One set of each, at the"
            " bottom of its range."
        )
    elif found.phase is Phase.LIGHT:
        at = f", session {found.count + 1} of {found.of}" if found.count < found.of else ""
        text = f"Easy start: light{at}{until}."
        if found.ending:
            text += " Next: one set fewer than planned of each."
    elif found.phase is Phase.LOWER:
        at = f", session {found.count + 1} of {found.of}" if found.count < found.of else ""
        text = f"Easy start: one set fewer of each{at}{until}."
        if found.fresh:
            text = "New today: " + text
        if found.ending:
            text += " Next: full sessions."
    else:
        return FULL if found.phase is Phase.DONE and found.fresh else None
    return text + WALK


def setting(session: Session) -> Setting:
    """The person's easy-start settings; off with no settings row."""
    row = users.settings_row(session)
    if row is None:
        return Setting(False)
    return Setting(
        row.easy_start, row.easy_start_from, row.easy_start_weeks_light, row.easy_start_weeks_lower
    )


def counted(session: Session) -> list[date]:
    """The local day of every done workout of one of the person's own strength or conditioning
    sessions: not a rest, a skip, a recovery session or an extra (a walk logged through the bot
    names no session). Several on a day count several times."""
    return list(
        session.scalars(
            select(Workout.local_date)
            .join(SessionTemplate, SessionTemplate.id == Workout.template_id)
            .where(Workout.status == WorkoutStatus.DONE, SessionTemplate.kind.in_(COUNTED))
        )
    )


def current(session: Session, on: date) -> State:
    """Where the easy start stands on ``on``, a local date."""
    return domain.state(setting(session), counted(session), on)


def _row(session: Session) -> UserSettings:
    row = users.settings_row(session)
    if row is None:
        row = UserSettings()
        session.add(row)
    return row


def tell_due(session: Session, on: date) -> Phase | None:
    """Write the notice for a step up reached by ``on`` (one set lower, the end), once each:
    the phase told, or None. Shown in the app until seen, told on Telegram by ADR-0087's check."""
    row = users.settings_row(session)
    if row is None or not row.easy_start:
        return None
    told = Phase(row.easy_start_told) if row.easy_start_told else None
    due = domain.notice(current(session, on).phase, told)
    if due is None:
        return None
    session.add(PlanNotice(text=TOLD[due]))
    row.easy_start_told = due.value
    session.flush()
    return due


def refused(session: Session, on: bool, today: date) -> str | None:
    """Why the switch can't be set to ``on`` today, in words; None when it can (or already is).
    Never for the owner (Decided 13), and not once the easy start is over (Decided 5): judged as
    if on, so turning it off and on can't start it again."""
    now = setting(session)
    if now.on == on:
        return None
    if bound_user(session) == users.OWNER:
        return OWNER
    since = now.since or today  # turned on the first time today: nothing before counts
    over = domain.state(replace(now, on=True, since=since), counted(session), today)
    return OVER if over.phase is Phase.DONE else None


def changeable(session: Session, today: date) -> bool:
    """Whether the switch can be changed: a member whose easy start isn't over."""
    return refused(session, not setting(session).on, today) is None


def turn(session: Session, on: bool, today: date) -> str | None:
    """Set the switch, or say why not (``refused``), changing nothing. The first time it goes
    on, the easy start counts from ``today``; off and on later keeps that day (Decided 5)."""
    problem = refused(session, on, today)
    if problem is not None or setting(session).on == on:
        return problem
    row = _row(session)
    row.easy_start = on
    if on and row.easy_start_from is None:
        row.easy_start_from = today
    session.add(Event(kind="settings.changed", payload={"easy_start": on}))
    session.flush()
    return None


def extend(session: Session, on: date) -> str | None:
    """ "One more easy week" for the phase that just ended (Decided 17), or why not."""
    phase = current(session, on).extend
    if phase is None:
        return NO_WEEK
    after = domain.extended(setting(session), phase)
    row = _row(session)
    row.easy_start_weeks_light, row.easy_start_weeks_lower = after.weeks_light, after.weeks_lower
    session.add(Event(kind="easy_start.extended", payload={"phase": phase.value}))
    session.flush()
    return None


def restart(session: Session, on: date) -> str | None:
    """ "Start the easy start again" after a gap (Decided 9): counted from ``on``, no easy weeks
    used and nothing told yet; or why not."""
    if not current(session, on).restart:
        return NO_RESTART
    after = domain.restarted(on)
    row = _row(session)
    row.easy_start_from, row.easy_start_told = after.since, None
    row.easy_start_weeks_light, row.easy_start_weeks_lower = after.weeks_light, after.weeks_lower
    session.add(Event(kind="easy_start.restarted", payload={}))
    session.flush()
    return None
