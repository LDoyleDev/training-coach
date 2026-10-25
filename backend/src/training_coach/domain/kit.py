"""What a person's home kit allows (ADR-0071). Pure logic, no I/O.

A kit is a list of items, each with a weight where it has one. A ladder step's ``needs`` (the
catalogue's, ADR-0064) are met when every need has an item: a kettlebell of that exact weight
(each weight is owned apart), dumbbells of that weight (a fixed pair, or an adjustable set whose
range covers it), a weighted vest or backpack that goes up to at least that load, a band of that
strength or a stronger one, and any one of the other kit. A need without a weight takes any
item of its kind.

``None`` for a kit means the person hasn't listed one yet: then nothing is locked, so the app
works as before until they add their kit.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.muscles import STRENGTHS, Kit, parse_need

KG_MAX = 100
MAX_ITEMS = 60  # more than anyone's home holds; a bound for a PUT of the whole list
NOTE_MAX = 40


class Resistance(StrEnum):
    """A resistance band's strength."""

    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


NAMES = {
    Kit.KETTLEBELL: "kettlebell",
    Kit.DUMBBELLS: "dumbbells",
    Kit.BACKPACK: "weighted vest or backpack",
    Kit.BAND: "band",
    Kit.PULL_UP_BAR: "pull-up bar",
    Kit.DIP_BARS: "dip bars or two chairs",
    Kit.BENCH: "bench, stools or bed to lie on",
    Kit.RINGS: "rings",
    Kit.BOX: "step or box",
    Kit.MAT: "mat",
    Kit.AB_WHEEL: "ab wheel",
}
PLURAL = frozenset({Kit.DUMBBELLS, Kit.RINGS})  # no "a" in front


@dataclass(frozen=True)
class Item:
    """One thing a person owns. ``kg``: a kettlebell's weight, a dumbbell pair's (or the top of
    an adjustable set's range, with ``min_kg`` its bottom), how far a vest or backpack loads."""

    kit: Kit
    kg: float | None = None
    min_kg: float | None = None
    resistance: Resistance | None = None
    note: str = ""  # what it is, in the person's words: "two stools"

    @property
    def key(self) -> tuple[Kit, float | None, float | None, Resistance | None]:
        return self.kit, self.kg, self.min_kg, self.resistance


def _kg(value: float) -> str:
    return f"{value:g}"


def label(item: Item) -> str:
    """The item in plain words: "16 kg kettlebell", "light band", "pull-up bar"."""
    name = NAMES[item.kit]
    if item.kit is Kit.BACKPACK and item.kg is not None:
        return f"{name}, up to {_kg(item.kg)} kg"
    if item.kit is Kit.DUMBBELLS and item.min_kg is not None and item.kg is not None:
        return f"adjustable dumbbells, {_kg(item.min_kg)}-{_kg(item.kg)} kg"
    if item.kg is not None:
        return f"{_kg(item.kg)} kg {name}"
    if item.resistance is not None:
        return f"{item.resistance} {name}"
    return name


def need_label(need: str) -> str:
    """A step's need in plain words: "a 16 kg kettlebell", "a pull-up bar", "12 kg dumbbells"."""
    kit, kg = parse_need(need)
    if kit is Kit.BACKPACK and kg is not None:
        return f"a weighted vest or backpack of {kg} kg"
    if kit is Kit.BAND and kg is not None:
        return f"a {STRENGTHS[kg - 1]} band"
    name = f"{kg} kg {NAMES[kit]}" if kg is not None else NAMES[kit]
    if kit in PLURAL:
        return name
    spoken_vowel = name[0] in "aeiou8" or name.startswith(("11 ", "18 "))  # "an 8 kg", "an 11 kg"
    return f"{'an' if spoken_vowel else 'a'} {name}"


def problem(item: Item) -> str | None:
    """Why an item can't be saved, or None. Each kind says only what it has."""
    weighed = item.kit in (Kit.KETTLEBELL, Kit.DUMBBELLS, Kit.BACKPACK)
    if weighed and item.kg is None:
        return f"{NAMES[item.kit]}: say the weight in kg"
    if not weighed and item.kg is not None:
        return f"{NAMES[item.kit]} has no weight"
    for kg in (item.kg, item.min_kg):
        if kg is not None and not (0 < kg <= KG_MAX and (kg * 2).is_integer()):
            return f"{label(item)}: a weight from 0.5 to {KG_MAX} kg, in steps of 0.5"
    if item.min_kg is not None and (
        item.kit is not Kit.DUMBBELLS or item.kg is None or item.min_kg >= item.kg
    ):
        return f"{label(item)}: a range goes from a lighter to a heavier weight"
    if item.kit is Kit.BAND and item.resistance is None:
        return "a band: say light, medium or heavy"
    if item.kit is not Kit.BAND and item.resistance is not None:
        return f"{NAMES[item.kit]} has no strength"
    if len(item.note) > NOTE_MAX:
        return f"{label(item)}: keep the note to {NOTE_MAX} characters"
    return None


def problems(items: Sequence[Item]) -> str | None:
    """Why a whole kit can't be saved, or None: a bad item, the same item twice, too many."""
    if len(items) > MAX_ITEMS:
        return f"at most {MAX_ITEMS} items"
    seen: set[tuple[Kit, float | None, float | None, Resistance | None]] = set()
    for item in items:
        if (found := problem(item)) is not None:
            return found
        if item.key in seen:
            return f"{label(item)} is listed twice"
        seen.add(item.key)
    return None


def parse_item(token: str) -> Item:
    """An item from the short form the unlocks question takes: ``kettlebell:16``,
    ``dumbbells:12``, ``dumbbells:2-24``, ``backpack:10``, ``band:light``, ``pull-up bar``.

    Raises ValueError for anything else, or an item ``problem`` refuses."""
    name, _, detail = token.partition(":")
    kit = Kit(name)
    item: Item
    if kit is Kit.BAND:
        item = Item(kit, resistance=Resistance(detail))
    elif kit is Kit.DUMBBELLS and "-" in detail:
        low, _, high = detail.partition("-")
        item = Item(kit, kg=float(high), min_kg=float(low))
    else:
        item = Item(kit, kg=float(detail) if detail else None)
    if (found := problem(item)) is not None:
        raise ValueError(found)
    return item


def _meets(item: Item, kit: Kit, kg: int | None) -> bool:
    if item.kit is not kit:
        return False
    if kit is Kit.BAND and kg is not None:  # ``kg`` is the strength's rank here
        return item.resistance is not None and STRENGTHS.index(item.resistance) + 1 >= kg
    if kg is None or item.kg is None:
        return kg is None
    if kit is Kit.BACKPACK:
        return item.kg >= kg
    if item.min_kg is not None:
        return item.min_kg <= kg <= item.kg
    return item.kg == kg


def missing(kit: Sequence[Item] | None, needs: Iterable[str]) -> list[str]:
    """The needs a kit doesn't meet, in plain words; empty when the step is open. Nothing is
    missing from a kit that isn't listed yet (``None``)."""
    if kit is None:
        return []
    return [
        need_label(need)
        for need in needs
        if not any(_meets(item, *parse_need(need)) for item in kit)
    ]


def next_open(ladder: Sequence[Sequence[str]], at: int, kit: Sequence[Item] | None) -> int | None:
    """The first step after ``at`` the kit allows (Move up skips locked ones), or None.
    ``ladder`` is each step's needs, easiest first."""
    return next((i for i in range(at + 1, len(ladder)) if not missing(kit, ladder[i])), None)


def unlocks_next(
    ladder: Sequence[Sequence[str]], at: int, kit: Sequence[Item] | None
) -> list[str] | None:
    """At the top for this kit (harder steps exist, none of them open): what the very next step
    needs that the kit lacks. None when a harder open step exists or the ladder ends here."""
    if at + 1 >= len(ladder) or next_open(ladder, at, kit) is not None:
        return None
    return missing(kit, ladder[at + 1])


def unlocked(
    ladders: Mapping[str, Sequence[tuple[str, Sequence[str]]]],
    kit: Sequence[Item] | None,
    adding: Item,
) -> list[tuple[str, str]]:
    """The steps ``adding`` would open: (exercise, step) pairs, in ladder order. An unlisted
    kit counts as empty here, so a first item shows everything it opens."""
    before = list(kit or [])
    after = [*before, adding]
    return [
        (exercise, step)
        for exercise, steps in ladders.items()
        for step, needs in steps
        if missing(before, needs) and not missing(after, needs)
    ]
