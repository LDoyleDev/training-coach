"""Message text for the bot. Pure functions over service data; plain text, no markup."""

from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.parser import Entry
from training_coach.services.queue_actions import RestOutcome
from training_coach.services.today import Day, ItemPlan, SessionPlan, Today
from training_coach.services.workout_log import Draft

NO_PLAN = (
    "There is no training plan in the database, so I can't pick a session. "
    "The plan seed probably failed: check the logs for seed.failed."
)

SOMETHING_WENT_WRONG = "Something went wrong on my side. Try again in a minute."
NUDGE = "Nothing logged today yet. {session} is still waiting: start it, rest or swap it."
STALE = "That message is out of date. Send /today for the current session."


def targets_text(item: ItemPlan) -> str:
    unit = {ExerciseKind.REPS: "", ExerciseKind.SECONDS: "s", ExerciseKind.DURATION_MIN: " min"}
    text = " / ".join(f"{value}{unit[item.kind]}" for value in item.targets)
    return f"{text} per side" if item.per_side else text


def today_text(today: Today) -> str:
    session = today.session
    lines = [f"Today: {session.name}", session.focus, ""]
    for item in session.items:
        lines.append(f"- {item.exercise} ({item.step}): {targets_text(item)}")
    if session.optional:
        lines += ["", "This one is optional: resting today is fine."]
    if today.logged_today:
        lines += ["", "Already logged today: " + ", ".join(today.logged_today)]
    return "\n".join(lines)


def week_text(days: list[Day]) -> str:
    lines = ["The next 7 days, if each session is done on its day:", ""]
    lines += [f"{day.date:%a %d %b}  {day.session}" for day in days]
    return "\n".join(lines)


def session_detail_text(plan: SessionPlan) -> str:
    """Everything needed to train: each exercise's ladder step, its cue and per-set targets."""
    lines = [f"{plan.name}: {plan.focus}", ""]
    for item in plan.items:
        lines.append(f"- {item.exercise} ({item.step}): {targets_text(item)}")
        if item.cue:
            lines.append(f"  {item.cue}")
    lines += ["", "Log it when you're done."]
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
    if draft.entries:
        lines += [f"Log for {draft.session_name}:", ""]
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


def log_saved_text(sets: int, exercises: int, session: str, next_session: str | None) -> str:
    saved = f"Saved {session}: {exercises} exercise{'s' * (exercises != 1)}, {sets} sets."
    return f"{saved} Next up: {next_session}." if next_session else saved
