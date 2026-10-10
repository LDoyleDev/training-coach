import pytest

from training_coach.domain.measurements import SPECS, Kind, from_tenths, to_tenths


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
