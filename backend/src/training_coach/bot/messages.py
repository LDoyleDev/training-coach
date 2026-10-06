"""Message text for the bot. Pure functions over service data; plain text, no markup."""

from training_coach.domain.enums import ExerciseKind
from training_coach.services.today import Day, ItemPlan, Today

NO_PLAN = (
    "There is no training plan in the database, so I can't pick a session. "
    "The plan seed probably failed: check the logs for seed.failed."
)


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
