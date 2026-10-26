"""The weekly review on the web (ux-flow-plan C4): the week the bot sends on Sundays and shows
on /review, from the same service (D6), and earlier weeks. Owner-only.

The AI comment is made once per weekly review and sent on Telegram. It is kept 7 days
(ADR-0056), so for that long the week it reviewed shows it here too; it is untrusted text, sent
as a plain string for the page to show as text."""

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.progress import ReadyView
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.habits import LABELS as HABIT_LABELS
from training_coach.domain.queue import local_date
from training_coach.domain.volume import TARGET_MAX_SETS, TARGET_MIN_SETS
from training_coach.services import ai_comment, ai_key, review
from training_coach.services.review import week_start

router = APIRouter(prefix="/api/review", tags=["review"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class ReviewSetsView(BaseModel):
    group: str
    sets: float  # fractional hard sets (ADR-0064)


class ReviewBestView(BaseModel):
    exercise: str
    step: str
    kind: ExerciseKind
    best_set: int | None
    total: int | None
    strength: bool  # set in a strength block (ADR-0028)


class ReviewHabitView(BaseModel):
    label: str
    done: int
    days: int


class ReviewWeekView(BaseModel):
    start: str  # Monday
    current: bool  # this week, so far
    previous: str  # the Monday before
    next: str | None  # the Monday after; None for this week
    planned: int
    done: int
    rested: int
    extras: int
    sets: list[ReviewSetsView]  # hard sets per muscle group, largest first
    sets_target: tuple[int, int]
    zone2_minutes: int
    zone2_target: tuple[int, int] | None
    moderate_minutes: int
    bests: list[ReviewBestView]
    ready: list[ReadyView]  # ready to move up now, this week only; links to /plan
    strength_block: bool
    habits: list[ReviewHabitView]  # empty in a week with no check-off
    ai_comments: bool  # an AI comment goes with Sunday's review on Telegram
    ai_comment: str | None  # this week's, while kept (7 days) and comments are on; plain text


@router.get("", response_model=ReviewWeekView)
def get_review(
    request: Request,
    user: Owner,
    week: date | None = None,  # any day of the week; this week by default
) -> ReviewWeekView:
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    start = week_start(week or today)
    current = start == week_start(today)
    if start > week_start(today):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That week hasn't started.")
    # A past week is counted to its Sunday, as the review sent that day.
    on = today if current else start + timedelta(days=6)
    with session_scope(_bound(request, user)) as session:
        week_review = review.weekly(session, on, settings.tz)
        ai = ai_key.status(session)
        comment = ai_comment.stored(session, start, datetime.now(UTC))
    # The same conditions as services.ai_comment.weekly.
    comments_on = settings.secrets_key is not None and ai.connected and ai.enabled and not ai.failed
    return ReviewWeekView(
        start=start.isoformat(),
        current=current,
        previous=(start - timedelta(days=7)).isoformat(),
        next=None if current else (start + timedelta(days=7)).isoformat(),
        planned=week_review.planned,
        done=week_review.done,
        rested=week_review.rested,
        extras=week_review.extras,
        sets=[ReviewSetsView(group=g, sets=n) for g, n in week_review.volume],
        sets_target=(TARGET_MIN_SETS, TARGET_MAX_SETS),
        zone2_minutes=week_review.zone2_minutes,
        zone2_target=week_review.zone2_target,
        moderate_minutes=week_review.moderate_minutes,
        bests=[
            ReviewBestView(
                exercise=b.exercise,
                step=b.step,
                kind=b.kind,
                best_set=b.bests.best_set,
                total=b.bests.total,
                strength=b.strength,
            )
            for b in week_review.bests
        ],
        # Progress reads today's standing, which says nothing about an earlier week.
        ready=[ReadyView(exercise=r.exercise, slug=r.slug) for r in week_review.ready]
        if current
        else [],
        strength_block=week_review.strength_block,
        habits=[
            ReviewHabitView(label=HABIT_LABELS[h.habit], done=h.done, days=h.days)
            for h in week_review.habits
        ],
        ai_comments=comments_on,
        ai_comment=comment if comments_on else None,
    )
