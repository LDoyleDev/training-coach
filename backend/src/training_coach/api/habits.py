"""Habits on the web (ux-flow-plan C5): today's check-offs with what counts, and ticking one.
Owner-only. The same service as the bot's buttons (D5), so a tick on either shows on both.
"Today" is the local day in ``settings.tz``."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.habits import Habit, hint, label
from training_coach.domain.queue import local_date
from training_coach.services import habits, user_settings
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
    done: bool  # ticked today
    week_done: int  # days ticked this week, today included


class HabitsView(BaseModel):
    day: str
    week_days: int  # days of this week so far, today included (1 on a Monday)
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


@router.get("", response_model=HabitsView)
def get_habits(request: Request, user: Owner) -> HabitsView:
    today = _today(request)
    with session_scope(_bound(request, user)) as session:
        return _view(session, today)


@router.put("/{habit}", response_model=HabitsView)
def put_habit(habit: Habit, body: HabitMark, request: Request, user: Owner) -> HabitsView:
    """Tick or untick a habit for today. Repeating the same tap changes nothing."""
    today = _today(request)
    with session_scope(_bound(request, user)) as session:
        habits.mark(session, today, habit, body.done, today)
        return _view(session, today)
