"""The weekly AI comment from the person's own Groq key (ADR-0047 B).

The comment sees the same summary as "Copy for my AI" (the last 4 weeks; health data only when
ticked). Its text is untrusted: cleaned, capped, labelled as coming from the person's key, sent
as plain text and never acted on or stored. A key Groq refuses is marked failed and the person
is told once; any other failure skips the comment quietly.
"""

import re
import unicodedata
from datetime import UTC, date, datetime

import structlog
from sqlalchemy.orm import Session, sessionmaker

from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import ai_key, ai_summary
from training_coach.services.groq import GroqClient, GroqUnavailableError
from training_coach.services.secret_box import SecretBox

log = structlog.get_logger(__name__)

LABEL = "AI comment (from your Groq key, a suggestion only):"
KEY_FAILED = (
    "Your Groq key stopped working (removed, or out of quota?), so there's no AI comment this "
    "week. Enter it again on the Account page of the web app."
)
LIMIT = 1200
WEEKS = 4
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
    if settings.secrets_key is None:
        return None
    now = datetime.now(UTC)
    with session_scope(sessions) as session:
        status = ai_key.status(session)
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
    return f"{LABEL}\n\n{text}" if text else None
