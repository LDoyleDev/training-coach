"""The mobility flow's time (ADR-0062): a one-sided movement counts both sides."""

from training_coach.domain.mobility_flow import Flow, Move


def _move(slug: str, seconds: int, *, per_side: bool = False) -> Move:
    return Move(slug, slug, seconds, per_side, "t", "s", "e", ("c",), "b", "x", "p")


def test_a_one_sided_movement_takes_its_time_on_each_side() -> None:
    assert _move("bridge", 60).total == 60
    assert _move("lunge", 45, per_side=True).total == 90
    flow = Flow(
        "mobility", "Stop if it hurts.", (_move("bridge", 60), _move("lunge", 45, per_side=True))
    )
    assert flow.seconds == 150
