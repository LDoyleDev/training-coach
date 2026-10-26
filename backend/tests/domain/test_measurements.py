from datetime import date

import pytest

from training_coach.domain.measurements import (
    CADENCE,
    CHECKLIST,
    REMEASURE,
    SPECS,
    Kind,
    amount,
    averages,
    first_sentence,
    from_tenths,
    how,
    navy_body_fat,
    remeasure,
    settings_problem,
    to_tenths,
)


def test_values_are_kept_in_tenths() -> None:
    assert to_tenths(Kind.BODYWEIGHT, 83.4) == 834
    assert to_tenths(Kind.WAIST, 85) == 850
    assert to_tenths(Kind.RESTING_HR, 52) == 520
    assert from_tenths(834) == 83.4


@pytest.mark.parametrize(
    ("kind", "value", "reason"),
    [
        (Kind.WAIST, 820, "Waist must be from 40 to 200 cm"),
        (Kind.BODYWEIGHT, 8.3, "Bodyweight must be from 30 to 250 kg"),
        (Kind.RESTING_HR, 52.5, "Resting heart rate is a whole number"),
    ],
)
def test_a_slip_is_caught(kind: Kind, value: float, reason: str) -> None:
    assert to_tenths(kind, value) == reason


def test_every_kind_has_a_spec() -> None:
    assert set(SPECS) == set(Kind)


def test_a_whole_number_kind_takes_a_whole_number() -> None:
    assert to_tenths(Kind.RESTING_HR, 52.0) == 520


# ------------------------------------------------- the protocol and the estimate (ADR-0076)


def test_the_new_kinds_have_their_ranges() -> None:
    assert to_tenths(Kind.NECK, 39.5) == 395
    assert to_tenths(Kind.NECK, 19) == "Neck must be from 20 to 70 cm"
    assert to_tenths(Kind.BODY_FAT_SCALE, 21.3) == 213
    assert to_tenths(Kind.BODY_FAT_SCALE, 61) == "Body fat (scale) must be from 3 to 60 %"


def test_every_kind_says_how_to_take_it_and_whether_to_recheck() -> None:
    assert set(REMEASURE) == set(Kind)
    assert REMEASURE[Kind.RESTING_HR] is None
    for kind in Kind:
        assert how(kind, 15).endswith("."), kind
        assert "{" not in how(kind), kind
    assert CHECKLIST
    assert "2 to 4 weeks" in CADENCE


def test_the_thigh_is_taken_at_the_persons_distance() -> None:
    assert "12 cm above the top of the kneecap" in how(Kind.THIGH, 12)
    assert "a set distance above the top of the kneecap" in how(Kind.THIGH)
    assert how(Kind.WAIST, 12) == "Horizontal at the navel, relaxed."


def test_the_first_sentence_is_cut_at_its_full_stop() -> None:
    assert first_sentence("One. Two.") == "One."
    assert first_sentence("Only one.") == "Only one."


def test_amounts_carry_their_unit() -> None:
    assert amount(Kind.BODYWEIGHT, 83.4) == "83.4 kg"
    assert amount(Kind.RESTING_HR, 52) == "52 bpm"
    assert amount(Kind.BODY_FAT_SCALE, 3.2) == "3.2 points"


OCT_12 = date(2026, 10, 12)
OCT_25 = date(2026, 10, 25)


def test_a_far_value_asks_for_a_remeasure_naming_the_day() -> None:
    assert remeasure(Kind.WAIST, OCT_25, 88.5, (OCT_12, 85.0)) == (
        "Waist is 3.5 cm off your last (12 Oct): different landmark? Re-measure."
    )
    assert remeasure(Kind.BODYWEIGHT, OCT_25, 81.0, (OCT_12, 83.4)) == (
        "Bodyweight is 2.4 kg off your last (12 Oct): different scale or time of day? Re-measure."
    )
    last_year = (date(2025, 11, 3), 24.0)
    assert remeasure(Kind.BODY_FAT_SCALE, OCT_25, 20.5, last_year) == (
        "Body fat (scale) is 3.5 points off your last (3 Nov 2025): different scale or time of "
        "day? Re-measure."
    )


@pytest.mark.parametrize(
    ("kind", "value", "last", "warns"),
    [
        (Kind.WAIST, 88.0, 85.0, True),  # exactly the threshold
        (Kind.WAIST, 87.9, 85.0, False),
        (Kind.NECK, 37.5, 39.0, True),
        (Kind.NECK, 37.6, 39.0, False),
        (Kind.UPPER_ARM, 36.5, 35.0, True),
        (Kind.THIGH, 58.0, 60.0, True),
        (Kind.CHEST, 102.9, 100.0, False),
        (Kind.BODYWEIGHT, 81.5, 83.4, False),
        (Kind.BODY_FAT_SCALE, 24.0, 21.0, True),
        (Kind.RESTING_HR, 80, 50, False),  # never checked
    ],
)
def test_each_kind_has_its_threshold(kind: Kind, value: float, last: float, warns: bool) -> None:
    assert (remeasure(kind, OCT_25, value, (OCT_12, last)) is not None) is warns


def test_nothing_earlier_means_no_warning() -> None:
    assert remeasure(Kind.WAIST, OCT_25, 120.0, None) is None


@pytest.mark.parametrize(
    ("height", "neck", "waist", "found"),
    [
        (182, 39, 93, 20.9),
        (182, 39, 94, 21.6),
        (182, 39, 39, None),  # waist no bigger than the neck
        (182, 40, 39, None),
        (None, 39, 93, None),  # no height
        (182, None, 93, None),
        (182, 39, None, None),
    ],
)
def test_the_navy_estimate(
    height: float | None, neck: float | None, waist: float | None, found: float | None
) -> None:
    assert navy_body_fat(height, neck, waist) == found


def test_the_average_is_of_the_seven_days_ending_each_day() -> None:
    entries = [
        (date(2026, 10, 1), 84.0),
        (date(2026, 10, 7), 83.0),
        (date(2026, 10, 8), 82.6),
    ]
    assert averages(entries) == [
        (date(2026, 10, 8), 82.8, 2),  # 2-8 Oct: 1 Oct is out
        (date(2026, 10, 7), 83.5, 2),
        (date(2026, 10, 1), 84.0, 1),
    ]
    assert averages([]) == []


@pytest.mark.parametrize(
    ("height", "offset", "problem"),
    [
        (182, 15, None),
        (None, 15, None),
        (119, 15, "height must be from 120 to 230 cm"),
        (231, 15, "height must be from 120 to 230 cm"),
        (182, 4, "the thigh is measured from 5 to 30 cm above the kneecap"),
        (182, 31, "the thigh is measured from 5 to 30 cm above the kneecap"),
    ],
)
def test_body_settings_are_checked(height: int | None, offset: int, problem: str | None) -> None:
    assert settings_problem(height, offset) == problem
