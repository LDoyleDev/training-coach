"""Habits on the web (ux-flow-plan C5): a day's check-offs with what counts, and ticking one.
Owner-only. The same service as the bot's buttons (D5), so a tick on either shows on both.
"Today" is the local day in ``settings.tz``; ``day`` picks an earlier one, back to the
account's first day, to fill in a forgotten tick (ADR-0068). A later day is refused."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.habits import Habit, hint, label
from training_coach.domain.queue import local_date
from training_coach.services import day_view, habits, user_settings
from training_coach.services.review import week_start

router = APIRouter(prefix="/api/habits", tags=["habits"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _today(request: Request) -> date:
    settings: Settings = request.app.state.settings
    return local_date(datetime.now(UTC), settings.tz)


class HabitView(BaseModel):
    key: Habit
    label: str  # "Protein target (165 g)"
    hint: str  # what counts as done
    done: bool  # ticked on the day
    week_done: int  # days ticked in the day's week, up to the day


class HabitsView(BaseModel):
    day: str
    week_days: int  # days of the day's week up to the day (1 on a Monday)
    habits: list[HabitView]


class HabitMark(BaseModel):
    done: bool


def _view(session: Session, today: date) -> HabitsView:
    done = habits.checked(session, today)
    protein_g = user_settings.load(session).protein_g
    tally = {h.habit: h for h in habits.week(session, week_start(today), today)}
    return HabitsView(
        day=today.isoformat(),
        week_days=tally[Habit.MORNING_LIGHT].days,
        habits=[
            HabitView(
                key=habit,
                label=label(habit, protein_g),
                hint=hint(habit, protein_g),
                done=habit in done,
                week_done=tally[habit].done,
            )
            for habit in Habit
        ],
    )


NOT_YET = "that day hasn't happened yet"
TOO_EARLY = "that's before your first day in the coach"


def _day(session: Session, request: Request, day: date | None) -> tuple[date, date]:
    """The day asked for (default today) and today; refused outside the account's days."""
    settings: Settings = request.app.state.settings
    today = _today(request)
    shown = day or today
    if shown > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOT_YET)
    if shown < day_view.first_day(session, settings.tz):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, TOO_EARLY)
    return shown, today


@router.get("", response_model=HabitsView)
def get_habits(request: Request, user: Owner, day: date | None = None) -> HabitsView:
    with session_scope(_bound(request, user)) as session:
        shown, _ = _day(session, request, day)
        return _view(session, shown)


@router.put("/{habit}", response_model=HabitsView)
def put_habit(
    habit: Habit, body: HabitMark, request: Request, user: Owner, day: date | None = None
) -> HabitsView:
    """Tick or untick a habit for ``day`` (default today). Repeating the same tap changes
    nothing."""
    settings: Settings = request.app.state.settings
    with session_scope(_bound(request, user)) as session:
        shown, today = _day(session, request, day)
        habits.backfill(
            session, shown, habit, body.done, today, day_view.first_day(session, settings.tz)
        )
        return _view(session, shown)
