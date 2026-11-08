"""Forgetting a person (ADR-0089): on unlink, leave and erase the bot drops everything it keeps
in memory by their user id (drafts, questions asked, picks), so nothing of theirs waits for
them or for anyone else. Every handler class that keeps state by user id registers with the
gate: a class added later can't be missed."""

import ast
import inspect
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application, TypeHandler

from tests.bot.fakes import MULTI
from training_coach.bot import app as bot_app
from training_coach.bot.app import FORGET, build_bot
from training_coach.bot.gate import Gate, Person

BOT = Path(bot_app.__file__).parent


def _gate(application: Application) -> Gate:  # type: ignore[type-arg]  # see build_bot
    (first,) = application.handlers[-1]
    assert isinstance(first, TypeHandler)
    gate = first.callback.__self__  # type: ignore[attr-defined]  # the bound Gate.check
    assert isinstance(gate, Gate)
    return gate


# How state kept by user id is declared: by the convention the bot follows, the outer key or
# member is the user id. Anything keyed by user id in another shape needs adding here.
BY_ID = ("dict[int,", "OrderedDict[int,", "set[int]", "defaultdict[int,")


def _dicts_by_id(node: ast.AST) -> list[str]:
    """The attributes declared ``self.x: dict[int, ...]`` (or another shape in ``BY_ID``) in
    ``node``: kept by user id."""
    return [
        n.target.attr
        for n in ast.walk(node)
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Attribute)
        and ast.unparse(n.annotation).startswith(BY_ID)
    ]


def _per_person(cls: type) -> list[str]:
    return _dicts_by_id(ast.parse(inspect.getsource(cls)))


def _keepers() -> set[str]:
    """Every class in bot/ but the gate that keeps something by user id."""
    return {
        node.name
        for path in BOT.glob("*.py")
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.ClassDef) and node.name != "Gate" and _dicts_by_id(node)
    }


def test_every_class_keeping_state_by_user_id_is_forgotten(
    seeded: sessionmaker[Session],
) -> None:
    gate = _gate(build_bot(MULTI, seeded))
    registered = {type(f.__self__).__name__ for f in gate.forgets}  # type: ignore[attr-defined]  # bound methods
    assert _keepers() == registered
    assert len(registered) >= 4  # drafts, band and proposal questions, settings asks


def test_forgetting_drops_one_person_and_keeps_the_rest(
    seeded: sessionmaker[Session],
) -> None:
    application = build_bot(MULTI, seeded)
    gate = _gate(application)
    keepers = [f.__self__ for f in gate.forgets]  # type: ignore[attr-defined]  # bound methods
    for keeper in keepers:
        for attr in _per_person(type(keeper)):
            getattr(keeper, attr).update({1: "the owner's", 2: "the member's"})
    gate.bound[2] = seeded
    gate.found[5] = Person(user_id=2, chat=77, sessions=seeded)
    application.bot_data[FORGET](2)
    for keeper in keepers:
        for attr in _per_person(type(keeper)):
            assert getattr(keeper, attr) == {1: "the owner's"}, (type(keeper).__name__, attr)
    assert 2 not in gate.bound
    assert 5 not in gate.found
