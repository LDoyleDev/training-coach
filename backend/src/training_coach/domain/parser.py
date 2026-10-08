"""Rule parser for typed workout logs (step 1-E). Pure logic, no I/O.

"pull-ups 8 8 7 6, dips 12 11 10" -> one entry per exercise with per-set values. The parser
never guesses: anything it can't read with confidence becomes a problem the user sees in the
confirmation message (ADR-0007: nothing is saved without "Save").

Formats per entry: plain numbers (``8 8 7``, ``8/8/7``), ``3x8`` (three sets of eight),
seconds (``30s``, ``1:30``, ``2 min``), minutes (``45``, ``45 min``, ``1h``, ``1:15``), and for
one-sided exercises ``each side`` (default) or ``left 10 9 right 9 9``. Lines copied from the
bot's own message work too: ``- Pistol squat (Sit to chair): 7, 7, 7 per side``.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from training_coach.domain.enums import ExerciseKind, Side

MAX_TEXT = 2000
MAX_ENTRIES = 30
MAX_SETS = 20
LIMITS = {ExerciseKind.REPS: 200, ExerciseKind.SECONDS: 3600, ExerciseKind.DURATION_MIN: 600}
UNIT = {
    ExerciseKind.REPS: "reps",
    ExerciseKind.SECONDS: "seconds",
    ExerciseKind.DURATION_MIN: "minutes",
}
FUZZY_CUTOFF = 0.8  # similarity needed for a typo match
FUZZY_MARGIN = 0.05  # two different exercises this close to each other: ambiguous
FUZZY_MIN_LENGTH = 5  # shorter words must match a name exactly ('pull' isn't 'Pull-up')
QUOTE_LENGTH = 40  # problems echo at most this much of the user's text

FILLER = frozenset(
    {
        "i",
        "did",
        "done",
        "do",
        "of",
        "the",
        "a",
        "an",
        "and",
        "then",
        "today",
        "reps",
        "rep",
        "sets",
        "set",
        "x",
        "times",
        "with",
        "my",
    }
)
# Entries split on new lines, semicolons and commas, except a comma before a number: that one
# separates sets, so "pull-ups 8, 8, 7" and "8,8,7" stay one exercise.
SPLIT_ENTRIES = re.compile(r"[;\n]+|,(?!\s*\d)")
# Copying the bot's own lines back ("- Tibialis raise (Back against wall): 20, 20, 20") is a
# natural way to log, so those decorations are tidied away before reading.
BULLET = re.compile(r"^[ \t]*[-\u2013\u2014\u2022*\u00b7][ \t]*", re.MULTILINE)
NUMBERED = re.compile(r"^[ \t]*\d{1,2}[.)][ \t]+", re.MULTILINE)  # "1. Jump squat: 7" (#97)
BRACKETS = re.compile(r"\([^()\n]*\)")
NAME_COLON = re.compile(r"(?<!\d):")  # "Tibialis raise: 20", never a time like 1:30
GLUED_SIDE = re.compile(r"(?<=\d)(?=(?:per|each)\b)", re.IGNORECASE)  # "7per side"
TOKEN = re.compile(
    # 3x8, or 3 times-sign 8: phones autocorrect "x" to the multiplication sign.
    r"(?P<sets>\d+)\s*[x\u00d7]\s*"
    r"(?P<each>\d+(?::\d{2})?)\s*(?P<eachunit>h|hrs?|hours?|m|min|mins|minutes?|s|sec|secs|seconds?)?\b"
    r"|(?P<clock>\d+:\d{2})"
    r"|(?P<num>\d+)\s*(?:(?P<unit>h|hrs?|hours?|m|min|mins|minutes?|s|sec|secs|seconds?)|reps?)?\b"
    r"|(?P<word>[a-z]+)",
)
SIDE_WORDS = {"left": Side.LEFT, "l": Side.LEFT, "right": Side.RIGHT, "r": Side.RIGHT}
EACH_WORDS = frozenset({"each", "per", "side", "sides", "leg", "legs", "arm", "arms"})


@dataclass(frozen=True)
class Known:
    """An exercise a log may name."""

    slug: str
    names: tuple[str, ...]  # name and aliases
    kind: ExerciseKind
    per_side: bool


@dataclass(frozen=True)
class Entry:
    slug: str
    sets: tuple[tuple[int, Side, int], ...]  # (set_no, side, value), as combine_sides takes


@dataclass(frozen=True)
class ParseResult:
    entries: tuple[Entry, ...]
    problems: tuple[str, ...]


def _quote(text: str) -> str:
    """A short, printable excerpt of user text for a problem message."""
    clean = " ".join("".join(c if c.isprintable() else " " for c in text).split())
    if len(clean) > QUOTE_LENGTH:
        clean = clean[:QUOTE_LENGTH] + "..."
    return f"'{clean}'"


def normalise_name(text: str) -> str:
    """The form names are compared in: lower case, no punctuation, filler or plurals.
    The seed uses it to keep every exercise name and alias unique."""
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    return " ".join(_singular(w) for w in words if w not in FILLER)


_normal = normalise_name


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _match(phrase: str, known: Sequence[Known]) -> Known | str:
    """The exercise a phrase names, or a problem message."""
    wanted = _normal(phrase)
    if not wanted:
        return "a line with numbers but no exercise name"
    scored: dict[str, tuple[float, Known]] = {}
    for exercise in known:
        for name in exercise.names:
            if _normal(name) == wanted:
                score = 1.0
            elif len(wanted) >= FUZZY_MIN_LENGTH:
                score = SequenceMatcher(None, wanted, _normal(name)).ratio()
            else:
                score = 0.0
            if score > scored.get(exercise.slug, (0.0, exercise))[0]:
                scored[exercise.slug] = (score, exercise)
    ranked = sorted(scored.values(), key=lambda pair: pair[0], reverse=True)
    if not ranked or ranked[0][0] < FUZZY_CUTOFF:
        return f"I don't know the exercise {_quote(phrase)}"
    if len(ranked) > 1 and ranked[0][0] < 1.0 and ranked[0][0] - ranked[1][0] < FUZZY_MARGIN:
        a, b = ranked[0][1].names[0], ranked[1][1].names[0]
        return f"{_quote(phrase)} could be {a} or {b}"
    return ranked[0][1]


def _value(number: str, unit: str | None, exercise: Known) -> int | str:
    """A number in the exercise's own unit (reps, seconds or minutes), or a problem."""
    u = (unit or "").lower()
    hours, minutes, seconds = u.startswith("h"), u.startswith("m"), u.startswith("s")
    name, kind = exercise.names[0], exercise.kind
    if kind == ExerciseKind.REPS and (u or ":" in number):
        return f"{name} is counted in reps, not time"
    if ":" in number:
        big, small = (int(part) for part in number.split(":"))
        if small > 59:
            return f"{_quote(number)} isn't a time"
        # 1:30 is minutes:seconds for timed holds, hours:minutes for durations.
        return big * 60 + small
    n = int(number)
    if kind == ExerciseKind.SECONDS:
        return n * 3600 if hours else n * 60 if minutes else n
    if seconds:  # durations are whole minutes; don't round seconds away
        return f"{name} is counted in minutes"
    return n * 60 if hours else n


def _split(text: str, start: int) -> tuple[str, str]:
    """Name and numbers. Side words just before the numbers belong to the numbers
    ("split squat left 10 9"), not to the name."""
    phrase, rest = text[:start], text[start:]
    side_tail = re.search(r"\b(left|right|l|r)\s*$", phrase.lower())
    if side_tail:
        phrase, rest = phrase[: side_tail.start()], phrase[side_tail.start() :] + rest
    return phrase, rest


def _entry(text: str, known: Sequence[Known]) -> tuple[Known, list[tuple[Side | None, int]]] | str:
    """One exercise and its values in order (side None = not given), or a problem."""
    starts = [m.start() for m in re.finditer(r"(?<![a-z0-9])\d", text.lower())]
    if not starts:
        return f"no numbers for {_quote(text)}"
    # A name can contain a number ("zone 2 45"): prefer the split where the whole name
    # matches exactly, otherwise the numbers start at the first number.
    exact = {_normal(name) for exercise in known for name in exercise.names}
    splits = [_split(text, start) for start in starts]
    phrase, rest = next((s for s in splits if _normal(s[0]) in exact), splits[0])
    exercise = _match(phrase, known)
    if isinstance(exercise, str):
        return exercise

    values: list[tuple[Side | None, int]] = []
    side: Side | None = None
    # "8/8/7" lists sets; "8-10" is more likely a range than two sets, so ask instead.
    dash = re.search(r"\d+\s*-\s*\d+", rest)
    if dash:
        return f"{_quote(dash.group())} looks like a range; give each set, like 8 9 10"
    rest = re.sub(r"(?<=\d)/(?=\d)", " ", rest.lower())
    name = exercise.names[0]
    for token in TOKEN.finditer(rest):
        if token["sets"]:
            # Check the count before building anything: "999999999x8" must not allocate.
            count = int(token["sets"]) if len(token["sets"]) <= 3 else MAX_SETS + 1
            if count == 0:
                return f"{name} needs at least one set"
            if count > MAX_SETS:
                return f"that's more than {MAX_SETS} sets of {name}"
            value = _value(token["each"], token["eachunit"], exercise)
            if isinstance(value, str):
                return value
            values += [(side, value)] * count
        elif token["clock"] or token["num"]:
            value = _value(token["clock"] or token["num"], token["unit"], exercise)
            if isinstance(value, str):
                return value
            values.append((side, value))
        elif token["word"] in SIDE_WORDS:
            if not exercise.per_side:
                return f"{name} isn't done one side at a time"
            side = SIDE_WORDS[token["word"]]
        elif token["word"] in EACH_WORDS or token["word"] in FILLER:
            continue
        else:
            return f"I don't understand {_quote(token['word'])} in {_quote(text)}"
        if len(values) > MAX_SETS:
            return f"that's more than {MAX_SETS} sets of {name}"
    if not values:  # e.g. "10x": digits that never formed a set
        return f"couldn't read any sets for {name}"
    return exercise, values


def _sets(
    exercise: Known, values: list[tuple[Side | None, int]]
) -> tuple[tuple[int, Side, int], ...]:
    if not exercise.per_side:
        return tuple((n, Side.BOTH, v) for n, (_, v) in enumerate(values, start=1))
    if all(side is None for side, _ in values):  # "each side" is the default for one-sided work
        return tuple(
            (n, s, v) for n, (_, v) in enumerate(values, start=1) for s in (Side.LEFT, Side.RIGHT)
        )
    rows: list[tuple[int, Side, int]] = []
    count = {Side.LEFT: 0, Side.RIGHT: 0}
    for side, value in values:
        for s in (side,) if side is not None else (Side.LEFT, Side.RIGHT):
            count[s] += 1
            rows.append((count[s], s, value))
    return tuple(rows)


def _unbalanced(exercise: Known, values: list[tuple[Side | None, int]]) -> str | None:
    """Explicit left/right sets must pair up: a missing side would count as 0 for progress."""
    left = sum(1 for side, _ in values if side is not Side.RIGHT)
    right = sum(1 for side, _ in values if side is not Side.LEFT)
    if not exercise.per_side or left == right:
        return None
    sets = "set" if left == 1 else "sets"
    return (
        f"{exercise.names[0]}: left has {left} {sets} and right has {right}; "
        "give both sides, or say 'each side'"
    )


def _notes(line: str) -> str:
    """Drop bracketed notes: a step name or "(8 kg)" before the sets, or words alone.
    Numbers in brackets after the sets ("dips 10 (then 8 8)") or holding every number on
    the line ("pull-ups (8 8 7)") are sets, so only their brackets go."""

    def note(match: re.Match[str]) -> str:
        before, inside = line[: match.start()], match.group()
        is_note = not re.search(r"\d", before) or not re.search(r"\d", inside)
        return " " if is_note else f" {inside[1:-1]} "

    dropped = BRACKETS.sub(note, line)
    if re.search(r"\d", line) and not re.search(r"\d", dropped):
        return BRACKETS.sub(lambda m: f" {m.group()[1:-1]} ", line)
    return dropped


def tidy(text: str) -> str:
    """Drop what isn't part of a log: list bullets, bracketed notes, the colon after a name,
    and the missing space in "7per side"."""
    text = NUMBERED.sub("", BULLET.sub("", text))
    text = "\n".join(_notes(line) for line in text.split("\n"))
    text = NAME_COLON.sub(" ", text)
    return GLUED_SIDE.sub(" ", text)


def parse_log(text: str, known: Sequence[Known]) -> ParseResult:
    """Every entry the text names, and every problem found. Never raises on user input."""
    if len(text) > MAX_TEXT:
        return ParseResult(
            (), (f"That's too long to read: keep a log under {MAX_TEXT} characters.",)
        )
    chunks = [c for c in SPLIT_ENTRIES.split(tidy(text)) if c.strip()]
    if not chunks:
        return ParseResult((), ("There's nothing to log in that message.",))
    if len(chunks) > MAX_ENTRIES:
        return ParseResult((), (f"That's more than {MAX_ENTRIES} exercises in one log.",))

    by_slug: dict[str, list[tuple[Side | None, int]]] = {}
    known_by_slug = {k.slug: k for k in known}
    problems: list[str] = []
    for chunk in chunks:
        parsed = _entry(chunk, known)
        if isinstance(parsed, str):
            problems.append(parsed)
            continue
        exercise, values = parsed
        by_slug.setdefault(exercise.slug, []).extend(values)  # a repeated exercise adds sets

    entries: list[Entry] = []
    for slug, values in by_slug.items():
        exercise = known_by_slug[slug]
        name, limit = exercise.names[0], LIMITS[exercise.kind]
        too_big = [v for _, v in values if v > limit]
        if too_big:
            problems.append(f"{too_big[0]} is more than {limit} {UNIT[exercise.kind]} for {name}")
        elif len(values) > MAX_SETS:
            problems.append(f"that's more than {MAX_SETS} sets of {name}")
        elif unbalanced := _unbalanced(exercise, values):
            problems.append(unbalanced)
        else:
            entries.append(Entry(slug, _sets(exercise, values)))
    return ParseResult(tuple(entries), tuple(problems))
