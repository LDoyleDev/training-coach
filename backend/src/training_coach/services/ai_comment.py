"""The weekly AI comment from the person's own Groq key (ADR-0047 B).

The comment sees the same summary as "Copy for my AI" (the last 4 weeks; health data only when
ticked). Its text is untrusted: cleaned, capped, labelled as coming from the person's key, sent
as plain text and never acted on. The cleaned text is also kept 7 days with its week, so the
web review can show it (ADR-0056); older ones are deleted at each weekly review. A key Groq
refuses is marked failed and the person is told once; any other failure skips the comment
quietly.
"""

import re
import unicodedata
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from training_coach.config import Settings
from training_coach.db.models import AiComment
from training_coach.db.session import session_scope
from training_coach.services import ai_key, ai_summary
from training_coach.services.groq import GroqClient, GroqUnavailableError
from training_coach.services.review import week_start
from training_coach.services.secret_box import SecretBox

log = structlog.get_logger(__name__)

LABEL = "AI comment (from your Groq key, a suggestion only):"
KEY_FAILED = (
    "Your Groq key stopped working (removed, or out of quota?), so there's no AI comment this "
    "week. Enter it again on the Account page of the web app."
)
LIMIT = 1200  # the ai_comments table's check allows this plus " …"
WEEKS = 4
KEEP = timedelta(days=7)  # stored comments, for the web review (ADR-0056)
# Everything Telegram would make tappable: any scheme (https://, tg://), www., bare domains
# (t.me/x, evil.example), @mentions and /commands. The comment is untrusted text.
URL = re.compile(
    r"\b[a-z][a-z0-9+.-]*://\S*|\bwww\.\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b(?:/\S*)?",
    re.IGNORECASE,
)
MENTION = re.compile(r"(?<![\w@])@\w+")
COMMAND = re.compile(r"(?<![\w/])/(?=[a-z])", re.IGNORECASE)
REFUSED = frozenset({"http_401", "http_403"})


def clean(text: str) -> str:
    """Plain, short text: no control characters or links, at most ``LIMIT`` characters."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if c == "\n" or unicodedata.category(c)[0] != "C")
    text = URL.sub("[link removed]", text)
    text = MENTION.sub("[mention removed]", text)
    text = COMMAND.sub("", text)  # "/undo" -> "undo": not a tappable command
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > LIMIT:
        text = text[:LIMIT].rsplit(" ", 1)[0].rstrip() + " …"
    return text


async def weekly(sessions: sessionmaker[Session], settings: Settings, today: date) -> str | None:
    """The message to send after the weekly review: the comment, the one-time notice that the
    key stopped working, or None (no key, off, already failed, or Groq didn't answer)."""
    now = datetime.now(UTC)
    with session_scope(sessions) as session:
        sweep(session, now)  # also in a week with no comment, so none outstays its 7 days
        status = ai_key.status(session)
        if settings.secrets_key is None:
            return None
        if not (status.connected and status.enabled) or status.failed:
            return None
        key = ai_key.key(session, SecretBox(settings.secrets_key), now)
        if key is None:  # marked failed just now: tell the person, once
            log.warning("ai.comment_skipped", reason="unreadable_key")
            return KEY_FAILED
        options = ai_summary.Options(WEEKS, body=status.body, readiness=status.readiness)
        summary = ai_summary.summary(session, today, options)
    client = GroqClient(key, comment_model=settings.groq_comment_model, attempts=2)
    try:
        raw = await client.comment(summary)
    except GroqUnavailableError as exc:
        log.warning("ai.comment_skipped", reason=exc.reason)
        if exc.reason not in REFUSED:
            return None
        with session_scope(sessions) as session:
            told = ai_key.failed(session, now)
        return KEY_FAILED if told else None
    text = clean(raw)
    log.info("ai.comment_made", chars=len(text))
    if not text:
        return None
    with session_scope(sessions) as session:
        store(session, week_start(today), text, datetime.now(UTC))
    return f"{LABEL}\n\n{text}"


def store(session: Session, week: date, text: str, now: datetime) -> None:
    """Keep ``week``'s cleaned comment (from ``clean``) for the web review, replacing one made
    earlier for the same week, and delete those past keeping."""
    row = session.scalar(select(AiComment).where(AiComment.week == week))
    if row is None:
        try:
            with session.begin_nested():  # the review sent twice at once: one inserts
                session.add(AiComment(week=week, text=text, created_at=now))
        except IntegrityError:
            row = session.scalar(select(AiComment).where(AiComment.week == week))
    if row is not None:
        row.text, row.created_at = text, now
    sweep(session, now)


def sweep(session: Session, now: datetime) -> None:
    """Delete the stored comments older than ``KEEP``."""
    session.execute(delete(AiComment).where(AiComment.created_at < now - KEEP))
    session.flush()


def stored(session: Session, week: date, now: datetime) -> str | None:
    """``week``'s stored comment while it is within its 7 days, else None."""
    return session.scalar(
        select(AiComment.text).where(AiComment.week == week, AiComment.created_at >= now - KEEP)
    )
