"""The /share progress image (ADR-0050): the last 4 weeks of training as a picture, to forward
to anyone. It holds sessions done, cardio minutes and where each exercise stands on its
ladder. Never body measurements, readiness answers, photos or notes.

``facts`` reads the database; ``render`` only draws, so it is tested on its own.
"""

import io
from dataclasses import dataclass
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import progress, review

DAYS = 28
MAX_EXERCISES = 8
SIZE = (1080, 1350)  # 4:5, what phones show full size in a chat

# The app's colours (frontend/src/index.css), dark version.
BACKGROUND = "#1b2024"
CARD = "#232a2f"
TEXT = "#eceeec"
MUTED = "#9ba7af"
ACCENT = "#ea7aa0"
LINE = "#353d43"


@dataclass(frozen=True)
class Rung:
    exercise: str
    step: str
    number: int  # 1-based
    of: int


@dataclass(frozen=True)
class Card:
    start: date
    end: date
    sessions: int  # planned sessions done
    extras: int  # unplanned workouts done
    zone2: int  # minutes
    moderate: int  # minutes
    rungs: list[Rung]


def facts(session: Session, today: date) -> Card:
    """The last ``DAYS`` days, ending today, for the person the session is bound to."""
    start = today - timedelta(days=DAYS - 1)
    done = (
        select(func.count())
        .select_from(Workout)
        .where(
            Workout.local_date >= start,
            Workout.local_date <= today,
            Workout.status == WorkoutStatus.DONE,
        )
    )
    planned = session.scalar(done.where(Workout.template_id.is_not(None))) or 0
    extras = session.scalar(done.where(Workout.template_id.is_(None))) or 0
    minutes = review.cardio_minutes(session, start, today)
    rungs = [
        Rung(s.exercise, s.step, s.step_number, s.steps)
        for s in progress.overview(session)
        if not s.retired and s.steps > 1
    ][:MAX_EXERCISES]
    return Card(
        start,
        today,
        planned,
        extras,
        minutes.get(review.ZONE2, 0),
        minutes.get(review.MODERATE, 0),
        rungs,
    )


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _fit(draw: ImageDraw.ImageDraw, text: str, size: int, width: int) -> str:
    """``text``, cut with an ellipsis if it would be wider than ``width`` pixels."""
    font = _font(size)
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def render(card: Card) -> bytes:
    """The card as a PNG."""
    image = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)
    left, right = 80, SIZE[0] - 80
    width = right - left

    draw.text((left, 80), "TRAINING COACH", font=_font(34), fill=ACCENT)
    draw.text((left, 130), "My last 4 weeks", font=_font(84), fill=TEXT)
    period = f"{card.start:%d %b} to {card.end:%d %b %Y}"
    draw.text((left, 235), period, font=_font(36), fill=MUTED)

    # Two big numbers side by side.
    stats = [
        (str(card.sessions), "sessions done" + (f" + {card.extras} extra" if card.extras else "")),
        (f"{card.zone2 + card.moderate}", "cardio minutes"),
    ]
    box = (width - 40) // 2
    for i, (number, label) in enumerate(stats):
        x = left + i * (box + 40)
        draw.rounded_rectangle((x, 320, x + box, 520), radius=32, fill=CARD)
        draw.text((x + 36, 340), number, font=_font(120), fill=TEXT)
        draw.text((x + 36, 470), _fit(draw, label, 32, box - 72), font=_font(32), fill=MUTED)

    draw.text((left, 580), "Where I am on each ladder", font=_font(44), fill=TEXT)
    y = 660
    for rung in card.rungs:
        name = _fit(draw, rung.exercise, 36, width // 2 - 20)
        draw.text((left, y), name, font=_font(36), fill=TEXT)
        step = _fit(draw, rung.step, 26, width // 2 - 20)
        draw.text((left, y + 44), step, font=_font(26), fill=MUTED)
        # One block per step, filled up to the current one.
        x0, gap = left + width // 2, 10
        block = (width // 2 - gap * (rung.of - 1)) / rung.of
        for n in range(rung.of):
            bx = x0 + n * (block + gap)
            fill = ACCENT if n < rung.number else LINE
            draw.rounded_rectangle((bx, y + 10, bx + block, y + 46), radius=8, fill=fill)
        y += 84
    if not card.rungs:
        draw.text((left, y), "Nothing logged yet.", font=_font(36), fill=MUTED)

    footer = "Shared from Training Coach. No body data or photos."
    draw.text((left, SIZE[1] - 100), footer, font=_font(28), fill=MUTED)

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
