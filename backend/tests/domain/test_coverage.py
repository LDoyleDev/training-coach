"""The body map's bands and warnings (program-builder.md, Decided 3 and F)."""

import pytest

from training_coach.domain.coverage import (
    GENERAL,
    OWN,
    Band,
    Day,
    Evidence,
    Item,
    band,
    coverage,
    needs_two_days,
    target,
)
from training_coach.domain.muscles import Muscle, Part, Stress

Q, G, T = Muscle.QUADS, Muscle.GLUTES, Muscle.TRICEPS


def _item(
    sets: int,
    muscles: dict[Muscle, float],
    parts: frozenset[Part] = frozenset(),
    stress: frozenset[Stress] = frozenset(),
) -> Item:
    return Item(exercise="x", sets=sets, muscles=muscles, parts=parts, stress=stress)


@pytest.mark.parametrize(
    ("sets", "expected"),
    [
        (0, Band.GREY),
        (0.5, Band.AMBER),
        (3.75, Band.AMBER),
        (4, Band.LIGHT_GREEN),
        (9.75, Band.LIGHT_GREEN),
        (10, Band.GREEN),
        (20, Band.GREEN),
        (20.5, Band.BLUE),
        (30, Band.BLUE),
        (30.25, Band.WARNING),
    ],
)
def test_the_six_bands_of_the_general_target(sets: float, expected: Band) -> None:
    assert band(sets, GENERAL) is expected


def test_small_muscles_have_their_own_band_and_evidence() -> None:
    assert band(3, target(Muscle.TIBIALIS)) is Band.GREEN
    assert band(7, target(Muscle.TIBIALIS)) is Band.BLUE
    assert band(2, target(Muscle.NECK)) is Band.AMBER  # below its 3, and below the minimum
    assert band(6, target(Muscle.CALVES)) is Band.LIGHT_GREEN
    assert band(4, target(Muscle.FRONT_DELTS)) is Band.GREEN  # covered by presses
    assert target(Muscle.CALVES).evidence is Evidence.MODERATE
    assert target(Muscle.TIBIALIS).evidence is Evidence.VERY_LOW
    assert target(Muscle.QUADS) is GENERAL
    assert GENERAL.evidence is None
    assert {m for m, t in OWN.items() if t.evidence is Evidence.LOW} == {
        Muscle.NECK,
        Muscle.FOREARMS,
        Muscle.SIDE_DELTS,
        Muscle.REAR_DELTS,
        Muscle.FRONT_DELTS,
    }


def test_two_days_are_needed_by_main_and_general_muscles_only() -> None:
    assert needs_two_days(Muscle.CALVES)  # a main muscle with its own band
    assert needs_two_days(Muscle.ABS)  # the general band
    assert not needs_two_days(Muscle.TIBIALIS)


def test_green_on_one_day_shows_light_green() -> None:
    found = coverage([Day("Legs", [_item(12, {Q: 1})]), Day("Rest", [])])
    quads = found.muscles[0]
    assert (quads.muscle, quads.sets, quads.days, quads.band) == (Q, 12, 1, Band.LIGHT_GREEN)
    assert quads.one_day
    assert quads.over_session_cap
    assert (quads.most, quads.most_in) == (12, "Legs")


def test_green_on_two_days_and_where_sets_come_from() -> None:
    found = coverage([Day("A", [_item(3, {Q: 1, G: 0.5})]), Day("B", [Item("Squat", 7, {Q: 1})])])
    by = {m.muscle: m for m in found.muscles}
    assert (by[Q].sets, by[Q].days, by[Q].band, by[Q].one_day) == (10, 2, Band.GREEN, False)
    assert [(s.session, s.exercise, s.sets, s.weight) for s in by[Q].sources] == [
        ("A", "x", 3, 1),
        ("B", "Squat", 7, 1),
    ]
    assert (by[G].sets, by[G].days) == (1.5, 0)  # 1.5 sets in a session is not a day
    assert found.main_on_target == 1


def test_untrained_muscles_are_grey_with_nothing_flagged() -> None:
    found = coverage([Day("A", [_item(3, {Q: 1, G: 0})])])
    glutes = next(m for m in found.muscles if m.muscle is G)
    assert (glutes.band, glutes.sets, glutes.most_in, glutes.one_day) == (Band.GREY, 0, None, False)
    assert (glutes.sources, glutes.missing_parts) == ((), ())


def test_main_muscles_come_first() -> None:
    found = coverage([])
    assert [m.main for m in found.muscles[:10]] == [True] * 10
    assert not any(m.main for m in found.muscles[10:])
    assert len(found.muscles) == len(Muscle)


def test_back_to_back_wraps_round_the_week() -> None:
    week = [Day("Mon", [_item(4, {Q: 1})]), Day("Tue", []), Day("Sun", [_item(5, {Q: 1})])]
    assert coverage(week).muscles[0].back_to_back == ("Sun", "Mon")
    assert coverage([Day("Mon", [_item(4, {Q: 1})])]).muscles[0].back_to_back is None
    spaced = [Day("Mon", [_item(4, {Q: 1})]), Day("Tue", [_item(3, {Q: 1})]), Day("Wed", [])]
    assert coverage(spaced).muscles[0].back_to_back is None


def test_a_part_is_flagged_until_an_exercise_reaches_it() -> None:
    pressing = Day("A", [_item(6, {T: 0.5})])
    assert coverage([pressing]).muscles[6].missing_parts == (Part.TRICEPS_LONG_HEAD,)
    overhead = Day("B", [_item(3, {T: 1}, parts=frozenset({Part.TRICEPS_LONG_HEAD}))])
    assert coverage([pressing, overhead]).muscles[6].missing_parts == ()


def test_spine_and_grip_load_per_session() -> None:
    week = [
        Day(
            "Legs",
            [
                _item(5, {G: 1}, stress=frozenset({Stress.SPINE, Stress.GRIP})),
                _item(4, {Q: 1}, stress=frozenset({Stress.SPINE})),
            ],
        ),
        Day("Arms", [_item(8, {T: 1}, stress=frozenset({Stress.GRIP}))]),
    ]
    legs, arms = coverage(week).days
    assert (legs.spine_sets, legs.grip_sets, legs.spine_heavy, legs.grip_heavy) == (
        9,
        5,
        True,
        False,
    )
    assert (arms.spine_sets, arms.grip_sets, arms.spine_heavy, arms.grip_heavy) == (
        0,
        8,
        False,
        False,
    )
