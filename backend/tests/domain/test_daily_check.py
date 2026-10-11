from itertools import product

import pytest

from training_coach.domain.daily_check import (
    QUESTIONS,
    TEXTS,
    TITLES,
    Advice,
    Answers,
    Energy,
    Sleep,
    Soreness,
    advise,
    summary,
)


def _a(sleep: str, soreness: str, energy: str) -> Answers:
    return Answers(Sleep(sleep), Soreness(soreness), Energy(energy))


@pytest.mark.parametrize(
    ("sleep", "soreness", "energy", "advice"),
    [
        ("good", "none", "high", Advice.AS_PLANNED),
        ("ok", "none", "high", Advice.AS_PLANNED),  # one middle is fine
        ("ok", "some", "high", Advice.LIGHTER),  # two middles
        ("ok", "some", "normal", Advice.LIGHTER),
        ("poor", "none", "high", Advice.LIGHTER),  # one worst
        ("good", "a_lot", "high", Advice.LIGHTER),
        ("good", "none", "low", Advice.LIGHTER),
        ("poor", "a_lot", "high", Advice.REST),  # two worst
        ("good", "a_lot", "low", Advice.REST),
        ("poor", "some", "low", Advice.REST),
        ("poor", "a_lot", "low", Advice.REST),
    ],
)
def test_the_rule(sleep: str, soreness: str, energy: str, advice: Advice) -> None:
    assert advise(_a(sleep, soreness, energy)) is advice


def test_every_combination_has_advice_matching_the_counts() -> None:
    """All 27: the position of each answer (0 best, 2 worst) decides, never which question."""
    for sleep, soreness, energy in product(Sleep, Soreness, Energy):
        ranks = [
            list(Sleep).index(sleep),
            list(Soreness).index(soreness),
            list(Energy).index(energy),
        ]
        if ranks.count(2) >= 2:
            expected = Advice.REST
        elif ranks.count(2) == 1 or ranks.count(1) >= 2:
            expected = Advice.LIGHTER
        else:
            expected = Advice.AS_PLANNED
        assert advise(Answers(sleep, soreness, energy)) is expected


def test_the_questions_cover_every_answer_best_first() -> None:
    assert [q.key for q in QUESTIONS] == ["sleep", "soreness", "energy"]
    for question, kind in zip(QUESTIONS, (Sleep, Soreness, Energy), strict=True):
        assert [value for value, _ in question.options] == list(kind)
        assert question.text.endswith("?")


def test_every_advice_has_a_title_and_text() -> None:
    assert set(TITLES) == set(TEXTS) == set(Advice)


def test_the_summary_says_the_answers_and_the_advice() -> None:
    assert summary(_a("ok", "some", "normal")) == (
        "Slept OK, a bit sore, normal energy: go lighter today"
    )
    assert (
        summary(_a("poor", "a_lot", "low"))
        == "Slept poorly, very sore, low energy: take a rest day"
    )
    assert summary(_a("good", "none", "high")) == "Slept well, not sore, high energy: go as planned"
