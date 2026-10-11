"""The daily check for the web app (ADR-0053): today's answers and advice, and answering.
Owner-only; health data, never shared. "Today" is the local day in ``settings.tz``."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.daily_check import (
    QUESTIONS,
    TEXTS,
    TITLES,
    Advice,
    Answers,
    Energy,
    Sleep,
    Soreness,
    advise,
    summary,
)
from training_coach.domain.queue import local_date
from training_coach.services import daily_check, health_summary

router = APIRouter(prefix="/api/daily-check", tags=["daily check"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class OptionView(BaseModel):
    value: str
    label: str


class CheckQuestionView(BaseModel):
    key: str
    text: str
    options: list[OptionView]  # best first


class CheckAnswers(BaseModel):
    sleep: Sleep
    soreness: Soreness
    energy: Energy


class AdviceView(BaseModel):
    kind: Advice
    title: str  # "Go lighter today"
    text: str
    summary: str  # "Slept OK, a bit sore, normal energy: go lighter today"


class DailyCheckView(BaseModel):
    """Today's check: the questions, and the answers with their advice once given."""

    day: str
    questions: list[CheckQuestionView]
    answers: CheckAnswers | None
    advice: AdviceView | None
    # From last night's sleep on the band (ADR-0054): the answer to pre-select, still tapped.
    suggested_sleep: Sleep | None = None
    band_asleep_min: int | None = None


def _view(day: str, answers: Answers | None) -> DailyCheckView:
    advice = None
    if answers is not None:
        kind = advise(answers)
        advice = AdviceView(
            kind=kind, title=TITLES[kind], text=TEXTS[kind], summary=summary(answers)
        )
    return DailyCheckView(
        day=day,
        questions=[
            CheckQuestionView(
                key=q.key,
                text=q.text,
                options=[OptionView(value=v, label=label) for v, label in q.options],
            )
            for q in QUESTIONS
        ],
        answers=CheckAnswers(**vars(answers)) if answers is not None else None,
        advice=advice,
    )


@router.get("", response_model=DailyCheckView)
def get_daily_check(request: Request, user: Owner) -> DailyCheckView:
    settings: Settings = request.app.state.settings
    day = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        answers = daily_check.on(session, day)
        band = health_summary.suggested_sleep(session, day)
    view = _view(day.isoformat(), answers)
    if band is not None:
        view.suggested_sleep, view.band_asleep_min = band
    return view


@router.put("", response_model=DailyCheckView)
def put_daily_check(body: CheckAnswers, request: Request, user: Owner) -> DailyCheckView:
    """Answer today's check; answering again the same day replaces the answers."""
    settings: Settings = request.app.state.settings
    now = datetime.now(UTC)
    day = local_date(now, settings.tz)
    answers = Answers(body.sleep, body.soreness, body.energy)
    with session_scope(_bound(request, user)) as session:
        daily_check.save(session, day, answers, now)
    return _view(day.isoformat(), answers)
