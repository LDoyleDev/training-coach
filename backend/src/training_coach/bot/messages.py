"""Message text for the bot. Pure functions over service data; plain text, no markup."""

from training_coach.domain.enums import ExerciseKind
from training_coach.services.queue_actions import RestOutcome
from training_coach.services.today import Day, ItemPlan, SessionPlan, Today

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
