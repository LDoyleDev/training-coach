"""Message text for the bot. Pure functions over service data; plain text, no markup."""

from datetime import date

from training_coach.domain.blocks import WEEKS
from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.habits import LABELS as HABIT_LABELS
from training_coach.domain.habits import WEEK_DAYS
from training_coach.domain.parser import Entry
from training_coach.domain.progression import Progress
from training_coach.domain.volume import TARGET_MAX_SETS, TARGET_MIN_SETS
from training_coach.domain.work_order import work_order
from training_coach.services.progress import Feedback, Standing
from training_coach.services.queue_actions import RestOutcome
from training_coach.services.review import Review
from training_coach.services.today import Day, ItemPlan, SessionPlan, Today
from training_coach.services.workout_log import Draft

NO_PLAN = (
    "There is no training plan in the database, so I can't pick a session. "
    "The plan seed probably failed: check the logs for seed.failed."
)

SOMETHING_WENT_WRONG = "Something went wrong on my side. Try again in a minute."
NUDGE = "Nothing logged today yet. {session} is still waiting: start it, rest or swap it."
NUDGE_TEST = "Nothing logged today yet. {name} is still waiting: {where}."
STALE = "That message is out of date. Send /today for the current session."


UNIT = {ExerciseKind.REPS: "", ExerciseKind.SECONDS: "s", ExerciseKind.DURATION_MIN: " min"}
WORK_DOWN = "Work down the list, alternating the two exercises of each pair."
FILL_IN = "Copy the list, put in what you did and send it back to log it."


def work_list(items: tuple[ItemPlan, ...]) -> list[str]:
    """One numbered line per set in the order they're done (#97), a gap between pairs. The
    lines read back as a log once the numbers are what was done."""
    groups = work_order([len(item.targets) for item in items], [item.pair for item in items])
    lines: list[str] = []
    number = 0
    for group in groups:
        if lines:
            lines.append("")
        for index, set_no in group:
            item = items[index]
            number += 1
            target = f"{item.targets[set_no - 1]}{UNIT[item.kind]}"
            side = " per side" if item.per_side else ""
            lines.append(f"{number}. {item.exercise} ({item.step}): {target}{side}")
    return lines


def _paired(items: tuple[ItemPlan, ...]) -> bool:
    return any(item.pair is not None for item in items)


WARM_UP = "Warm up for about 10 minutes first."
BASELINE = (
    "Baseline for {names}: the first session at this step. Aim for the targets and log what "
    "you manage; the next targets grow from it."
)


def _baseline(items: tuple[ItemPlan, ...]) -> list[str]:
    """A line naming the exercises whose targets this session sets (ADR-0034)."""
    names = [item.exercise for item in items if item.baseline]
    if not names:
        return []
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return [BASELINE.format(names=joined)]


def today_text(today: Today) -> str:
    session = today.session
    lines = [f"Today: {session.name}", session.focus]
    if today.block is not None:
        lines.append(f"Week {today.block.week} of {WEEKS}, {today.block.kind} block.")
    if session.kind == "strength":
        lines.append(WARM_UP)
    if _paired(session.items):
        lines.append(WORK_DOWN)
    lines += _baseline(session.items)
    lines.append("")
    lines += work_list(session.items)
    if session.optional:
        lines += ["", "This one is optional: resting today is fine."]
    if today.logged_today:
        lines += ["", "Already logged today: " + ", ".join(today.logged_today)]
    return "\n".join(lines)


def tests_where(public_url: str | None) -> str:
    """Where test results are entered: the web app's tests page (ADR-0037)."""
    return f"{public_url}/tests" if public_url else "the Tests page of the web app"


def test_day_text(today: Today, where: str) -> str:
    """A test day in place of the session (ADR-0038): the tests, where to enter them, and that
    the session waits."""
    test = today.test_day
    assert test is not None  # noqa: S101 - callers check
    lines = [
        f"Today: {test.name}",
        ", ".join(test.tests) + ".",
        WARM_UP,
        "Do them in order and rest as long as you need between them.",
        f"Enter the results in the app: {where}",
        "",
        f"The plan waits: {today.session.name} comes after the tests.",
    ]
    if today.logged_today:
        lines += ["", "Already logged today: " + ", ".join(today.logged_today)]
    return "\n".join(lines)


def week_text(days: list[Day]) -> str:
    lines = ["The next 7 days, if each session is done on its day:", ""]
    lines += [f"{day.date:%a %d %b}  {day.session}" for day in days]
    return "\n".join(lines)


def session_detail_text(plan: SessionPlan) -> str:
    """Everything needed to train: the cues, then every set in the order it's done (#97)."""
    lines = [f"{plan.name}: {plan.focus}"]
    cues = [
        f"- {item.exercise}: {' '.join(part for part in (item.summary, item.cue) if part)}"
        for item in plan.items
        if item.summary or item.cue
    ]
    if cues:
        lines += ["", "How to do them:", *cues]
    lines += ["", WORK_DOWN if _paired(plan.items) else "Work down the list."]
    lines += [*_baseline(plan.items), ""]
    lines += work_list(plan.items)
    lines += ["", FILL_IN]
    return "\n".join(lines)


def rest_text(outcome: RestOutcome) -> str:
    if outcome.advanced:
        return f"{outcome.session} logged as a rest day. Enjoy it."
    return f"Rest today. {outcome.session} moves to tomorrow and the rest of the week shifts a day."


def pushed_text(session: str) -> str:
    return f"{session} moves to tomorrow and the rest of the week shifts a day."


def picked_text(plan: SessionPlan, offered: str) -> str:
    return f"{session_detail_text(plan)}\n\n{offered} is still next in the plan."


# ------------------------------------------------------------------ logging (1-E)

LOG_SAVED_BEFORE = "That log was already saved."
LOG_STALE = "Things changed since you sent that log (a rest, swap or another log). Send it again."
LOG_EXPIRED = "That log has expired. Send it again."
LOG_EDIT = "Send the corrected log as a new message."
LOG_CANCELLED = "Discarded. Nothing was saved."
LOG_TEXT_LIMIT = 4000  # Telegram allows 4096 characters per message
MODEL_ASSISTED = (
    "I needed the language model to read that. Check every number, and that nothing you "
    "did is missing, before saving."
)
VOICE_FAILED = "Couldn't transcribe that. Please type the log instead."
VOICE_OFF = "Voice logging isn't set up yet. Please type the log instead."
VOICE_TOO_LONG = "That voice note is too long. Keep it under two minutes, or type the log."
HEARD_LENGTH = 300


def heard_text(heard: str) -> str:
    """What the voice note said, so a mishearing is easy to spot before saving."""
    clean = " ".join("".join(c if c.isprintable() else " " for c in heard).split())
    if len(clean) > HEARD_LENGTH:
        clean = clean[:HEARD_LENGTH] + "..."
    return f'I heard: "{clean}"'


def _sets_text(entry: Entry, kind: ExerciseKind) -> str:
    unit = {ExerciseKind.REPS: "", ExerciseKind.SECONDS: "s", ExerciseKind.DURATION_MIN: " min"}
    by_side: dict[Side, list[int]] = {}
    for _, side, value in sorted(entry.sets):
        by_side.setdefault(side, []).append(value)

    def join(values: list[int]) -> str:
        return " / ".join(f"{v}{unit[kind]}" for v in values)

    if set(by_side) == {Side.BOTH}:
        return join(by_side[Side.BOTH])
    left, right = by_side.get(Side.LEFT, []), by_side.get(Side.RIGHT, [])
    if left == right:
        return f"{join(left)} each side"
    return f"left {join(left)}, right {join(right)}"


def log_text(draft: Draft, exercises: dict[str, tuple[str, ExerciseKind]]) -> str:
    """What the bot understood, for the user to confirm (ADR-0007). Plain text only."""
    lines: list[str] = []
    when = f" on {draft.on:%a %d %b}" if draft.backdated else ""
    if draft.rest and not draft.problems:
        session = "" if draft.template_id is None else f" ({draft.session_name})"
        return f"A rest day{session}{when}.\n\nSave it?"
    if draft.entries:
        lines += [f"Log for {draft.session_name}{when}:", ""]
        for entry in draft.entries:
            name, kind = exercises[entry.slug]
            lines.append(f"- {name}: {_sets_text(entry, kind)}")
    if draft.problems:
        if lines:
            lines.append("")
        lines.append("Not understood:" if draft.entries else "I couldn't read that log:")
        lines += [f"- {problem}" for problem in draft.problems]
    if draft.entries:
        closing = ["", "Save it?" if not draft.problems else "Save the part I understood?"]
    else:
        closing = ["", "Try again, like: pull-ups 8 8 7, dips 12 11 10"]
    return "\n".join(_fit(lines, closing))


def _fit(lines: list[str], closing: list[str], limit: int = LOG_TEXT_LIMIT) -> list[str]:
    """Keep a reply under Telegram's 4096-character limit (a long log can outgrow it)."""
    budget = limit - sum(len(line) + 1 for line in closing) - 40
    kept: list[str] = []
    for index, line in enumerate(lines):
        if budget - (len(line) + 1) < 0:
            kept.append(f"... {len(lines) - index} more not shown")
            break
        kept.append(line)
        budget -= len(line) + 1
    return kept + closing


def log_saved_text(
    sets: int, exercises: int, session: str, next_session: str | None, on: date | None = None
) -> str:
    """``on`` is set for a past day logged late (#104)."""
    when = f" for {on:%a %d %b}" if on is not None else ""
    if not exercises:  # a past rest day
        saved = f"Saved a rest day{when}."
    else:
        saved = (
            f"Saved {session}{when}: {exercises} exercise{'s' * (exercises != 1)}, "
            f"{sets} set{'s' * (sets != 1)}."
        )
    return f"{saved} Next up: {next_session}." if next_session else saved


def _amount(value: int, kind: ExerciseKind) -> str:
    if kind is ExerciseKind.SECONDS:
        return f"{value}s"
    if kind is ExerciseKind.DURATION_MIN:
        return f"{value} min"
    return f"{value} rep{'s' * (value != 1)}"


def saved_reply(saved: str, items: list[Feedback]) -> str:
    """The saved message plus feedback, kept under Telegram's limit: the save has already
    committed, so a reply that fails to send would wrongly look like a failed save."""
    extra = feedback_text(items)
    if not extra:
        return saved
    return "\n".join(_fit([saved, "", *extra.split("\n")], []))


def feedback_text(items: list[Feedback]) -> str:
    """Bests and progression after a save (ADR-0025). Empty when there is nothing to say."""
    lines: list[str] = []
    for item in items:
        parts = []
        if item.bests.best_set is not None:
            parts.append(f"{_amount(item.bests.best_set, item.kind)} in one set")
        if item.bests.total is not None:
            parts.append(f"{_amount(item.bests.total, item.kind)} in total")
        if parts:
            lines.append(f"New best on {item.exercise}: {' and '.join(parts)}.")
    for item in items:
        if item.status is Progress.READY:
            lines.append(
                f"{item.exercise}: top of the range two sessions running. "
                f"Ready to move up to {item.next_step}?"
            )
        elif item.note_top:
            lines.append(
                f"{item.exercise}: top of the range on the last step in your plan. Add a harder "
                "variation to plan.toml when you're ready."
            )
    return "\n".join(lines)


PROGRESS_EMPTY = "No exercises in the plan yet."


def _values(values: tuple[int, ...], kind: ExerciseKind) -> str:
    unit = {ExerciseKind.REPS: "", ExerciseKind.SECONDS: "s", ExerciseKind.DURATION_MIN: " min"}
    return " / ".join(f"{v}{unit[kind]}" for v in values)


def progress_text(standings: list[Standing]) -> str:
    """/progress: one line per exercise, under Telegram's limit."""
    if not standings:
        return PROGRESS_EMPTY
    lines = ["Progress: current step, last session, best set at this step", ""]
    for s in standings:
        retired = " (retired)" if s.retired else ""
        line = f"- {s.exercise}{retired}: {s.step} ({s.step_number}/{s.steps})"
        if s.last:
            line += f", last {_values(s.last, s.kind)}"
            if s.best_set is not None:
                line += f", best {_amount(s.best_set, s.kind)}"
        else:
            line += ", not logged at this step yet"
        if s.status is Progress.READY:
            line += ". Ready to move up"
        elif s.status is Progress.TOP_OF_LADDER:
            line += ". Top of the ladder"
        lines.append(line)
    return "\n".join(_fit(lines, []))


def cardio_line(review: Review) -> str:
    """Zone 2 against the weekly target, and moderate cardio (#124). Short of the target says by
    how much, once, without nagging; a week with none shows 0."""
    zone2 = f"Zone 2: {review.zone2_minutes}"
    if review.zone2_target is not None:
        low, high = review.zone2_target
        zone2 += f" of {low}-{high} min"
        if review.zone2_minutes < low:
            zone2 += f" ({low - review.zone2_minutes} short)"
    else:
        zone2 += " min"
    return f"{zone2} · Moderate: {review.moderate_minutes} min"


def review_text(review: Review) -> str:
    """The weekly review (#73): sessions, hard sets per muscle, bests, what's ready, habits."""
    lines = [f"Week of {review.start:%a %d %b}", ""]
    sessions = f"Sessions: {review.done} of {review.planned} done"
    extra = []
    if review.rested:
        extra.append(f"{review.rested} rest day{'s' * (review.rested != 1)}")
    if review.extras:
        extra.append(f"{review.extras} extra")
    lines.append(sessions + (f" ({', '.join(extra)})" if extra else "") + ".")
    if review.volume:
        lines += ["", f"Hard sets per muscle (aim {TARGET_MIN_SETS}-{TARGET_MAX_SETS}):"]
        for group, sets in review.volume:
            note = (
                " (low)" if sets < TARGET_MIN_SETS else " (high)" if sets > TARGET_MAX_SETS else ""
            )
            lines.append(f"- {group}: {sets}{note}")
    else:
        lines += ["", "No sets logged this week."]
    lines += ["", cardio_line(review)]
    if review.bests:
        lines += ["", "New bests:"]
        for best in review.bests:
            parts = []
            if best.bests.best_set is not None:
                parts.append(f"{_amount(best.bests.best_set, best.kind)} in one set")
            if best.bests.total is not None:
                parts.append(f"{_amount(best.bests.total, best.kind)} in total")
            where = f"{best.step}, strength block" if best.strength else best.step
            lines.append(f"- {best.exercise} ({where}): {' and '.join(parts)}")
    if review.ready and review.strength_block:
        names = ", ".join(review.ready)
        lines += ["", f"Ready to move up when the hypertrophy block starts: {names}."]
    elif review.ready:
        lines += ["", f"Ready to move up: {', '.join(review.ready)}. See /progress."]
    if review.habits:
        lines += ["", "Habits:"]
        for week in review.habits:
            so_far = "" if week.days == WEEK_DAYS else " so far"
            lines.append(f"- {HABIT_LABELS[week.habit]}: {week.done} of {week.days}{so_far}")
    return "\n".join(_fit(lines, []))
